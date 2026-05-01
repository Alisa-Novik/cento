#!/usr/bin/env python3
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

from fastapi import FastAPI, HTTPException, Path as FastAPIPath, Query
from fastapi.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = ROOT_DIR / "db" / "tracker.db"

app = FastAPI(title="Cento Agent Tracker", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(?:localhost|127\.0\.0\.1)(:[0-9]+)?$",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

SCHEMA = """
create table if not exists issues (
  id integer primary key,
  subject text not null,
  project text not null default 'cento-agent-work',
  tracker text not null default 'Agent Task',
  status text not null default 'Queued',
  priority text not null default 'Normal',
  assignee text not null default 'Redmine Admin',
  node text not null default '',
  agent text not null default '',
  role text not null default '',
  package text not null default '',
  done_ratio integer not null default 0,
  description text not null default '',
  updated_on text not null,
  closed_on text not null default '',
  source text not null default 'replacement',
  dispatch text not null default '',
  validation_report text not null default '',
  migrated_at text
);

create table if not exists journals (
  id integer primary key autoincrement,
  issue_id integer not null,
  author text not null default 'local operator',
  created_on text not null,
  notes text not null default '',
  old_status text not null default '',
  new_status text not null default '',
  source text not null default 'api',
  foreign key(issue_id) references issues(id)
);

create table if not exists validation_evidences (
  id integer primary key autoincrement,
  issue_id integer not null,
  label text not null default '',
  path text not null default '',
  url text not null default '',
  created_on text not null,
  source text not null default 'api',
  note text not null default '',
  foreign key(issue_id) references issues(id),
  unique(issue_id, path)
);

create index if not exists idx_issues_status on issues(status);
create index if not exists idx_issues_updated_on on issues(updated_on);
create index if not exists idx_journals_issue_created on journals(issue_id, created_on);
create index if not exists idx_validation_evidences_issue on validation_evidences(issue_id);
"""

ISSUE_STATUS_RATIO = {
    "queued": 0,
    "running": 25,
    "review": 50,
    "blocked": 10,
    "validating": 90,
    "done": 100,
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=120)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma busy_timeout = 120000")
    conn.execute("pragma journal_mode = WAL")
    conn.execute("pragma foreign_keys = ON")
    conn.execute("pragma synchronous = NORMAL")
    return conn


def ensure_table_column(conn: sqlite3.Connection, table: str, name: str, ddl: str) -> None:
    try:
        columns = {row[1] for row in conn.execute(f"pragma table_info({table})").fetchall()}
    except sqlite3.OperationalError:
        return
    if name not in columns:
        conn.execute(f"alter table {table} add column {name} {ddl}")


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    ensure_table_column(conn, "issues", "closed_on", "text not null default ''")
    ensure_table_column(conn, "issues", "source", "text not null default 'replacement'")
    ensure_table_column(conn, "issues", "dispatch", "text not null default ''")
    ensure_table_column(conn, "issues", "validation_report", "text not null default ''")
    ensure_table_column(conn, "issues", "migrated_at", "text")
    ensure_table_column(conn, "journals", "source", "text not null default 'api'")
    ensure_table_column(conn, "journals", "old_status", "text not null default ''")
    ensure_table_column(conn, "journals", "new_status", "text not null default ''")
    ensure_table_column(conn, "validation_evidences", "source", "text not null default 'api'")


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = connect_db()
    try:
        init_db(conn)
        yield conn
    finally:
        conn.commit()
        conn.close()


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def issue_done_ratio(status: str) -> int:
    return ISSUE_STATUS_RATIO.get(status.strip().lower(), 0)


def parse_payload_note(payload: dict[str, Any]) -> str:
    note = str(payload.get("note") or payload.get("notes") or "").strip()
    return note


def sync_validation_evidence(conn: sqlite3.Connection, issue_id: int, validation_report: str) -> None:
    path = str(validation_report or "").strip()
    if not path:
        return
    now = now_iso()
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
            Path(path).name or "validation-report.md",
            path,
            "",
            now,
            "api",
            "Validation report recorded by API.",
        ),
    )


def build_issue_where(
    *,
    status: str | None,
    tracker: str | None,
    project: str | None,
    assignee: str | None,
    search: str | None,
) -> tuple[str, list[str]]:
    filters: list[str] = []
    params: list[Any] = []

    if status is None:
        status = "open"
    lowered = status.lower()
    if lowered == "open":
        filters.append("lower(coalesce(status, '')) != 'done'")
    elif lowered != "all":
        filters.append("lower(coalesce(status, '')) = ?")
        params.append(lowered)

    if tracker:
        filters.append("tracker = ?")
        params.append(tracker)
    if project:
        filters.append("project = ?")
        params.append(project)
    if assignee:
        filters.append("assignee = ?")
        params.append(assignee)
    if search:
        term = f"%{search.strip().lower()}%"
        filters.append("(lower(coalesce(subject, '')) like ? or lower(coalesce(description, '')) like ?)")
        params.extend([term, term])

    where_sql = f" where {' and '.join(filters)}" if filters else ""
    return where_sql, params


def list_issues(
    conn: sqlite3.Connection,
    *,
    status: str | None,
    tracker: str | None,
    project: str | None,
    assignee: str | None,
    search: str | None,
    offset: int,
    limit: int | None,
) -> dict[str, Any]:
    where_sql, params = build_issue_where(
        status=status,
        tracker=tracker,
        project=project,
        assignee=assignee,
        search=search,
    )

    total = int(conn.execute(f"select count(*) as total from issues{where_sql}", params).fetchone()["total"])
    query = f"select * from issues{where_sql} order by datetime(updated_on) desc, id desc"
    rows_sql = params
    if limit and limit > 0:
        query += " limit ? offset ?"
        rows_sql = [*params, limit, max(offset, 0)]
    rows = [row_to_dict(item) for item in conn.execute(query, rows_sql).fetchall()]
    status_counts = {
        item["status"]: item["count"]
        for item in conn.execute(f"select status, count(*) as count from issues{where_sql} group by status", params).fetchall()
    }
    tracker_counts = {
        item["tracker"]: item["count"]
        for item in conn.execute(f"select tracker, count(*) as count from issues{where_sql} group by tracker", params).fetchall()
    }

    return {
        "issues": rows,
        "total": total,
        "offset": max(offset, 0),
        "limit": limit,
        "status_counts": status_counts,
        "tracker_counts": tracker_counts,
    }


def get_issue(conn: sqlite3.Connection, issue_id: int) -> dict[str, Any]:
    row = conn.execute("select * from issues where id = ?", (issue_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Issue not found: {issue_id}")
    activity = [
        row_to_dict(item)
        for item in conn.execute(
            "select * from journals where issue_id = ? order by datetime(created_on) asc, id asc",
            (issue_id,),
        ).fetchall()
    ]
    validation_evidences = [
        row_to_dict(item)
        for item in conn.execute(
            "select * from validation_evidences where issue_id = ? order by datetime(created_on) asc, id asc",
            (issue_id,),
        ).fetchall()
    ]
    return {"issue": row_to_dict(row), "activity": activity, "validation_evidences": validation_evidences}


@app.get("/api/issues")
def api_list_issues(
    status: str | None = Query(default="open"),
    tracker: str | None = Query(default=None),
    project: str | None = Query(default=None),
    assignee: str | None = Query(default=None),
    search: str | None = Query(default=None),
    q: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int | None = Query(default=None, ge=1),
) -> dict[str, Any]:
    search_term = search if search is not None else q
    with get_db() as conn:
        return list_issues(
            conn,
            status=status,
            tracker=tracker,
            project=project,
            assignee=assignee,
            search=search_term,
            offset=offset,
            limit=limit,
        )


@app.get("/api/issues/{issue_id}")
def api_get_issue(issue_id: int = FastAPIPath(ge=1)) -> dict[str, Any]:
    with get_db() as conn:
        return get_issue(conn, issue_id)


@app.post("/api/issues")
def api_create_issue(payload: dict[str, Any]) -> dict[str, Any]:
    subject = str(payload.get("subject") or "").strip()
    if not subject:
        raise HTTPException(status_code=400, detail="subject is required")

    status = str(payload.get("status") or "Queued")
    assignee = str(payload.get("assignee") or payload.get("agent") or "local operator")
    now = now_iso()

    with get_db() as conn:
        with conn:
            issue_id = int(payload.get("id") or 0)
            if issue_id <= 0:
                next_id = conn.execute("select coalesce(max(id), 0) + 1 as next_id from issues").fetchone()
                issue_id = int(next_id["next_id"]) if next_id else 1

            payload_status = status.strip()
            conn.execute(
                """
                insert into issues(
                    id, subject, project, tracker, status, priority, assignee, node, agent, role,
                    package, done_ratio, description, updated_on, closed_on, source, dispatch,
                    validation_report, migrated_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    issue_id,
                    subject,
                    str(payload.get("project") or "cento-agent-work"),
                    str(payload.get("tracker") or "Agent Task"),
                    payload_status,
                    str(payload.get("priority") or "Normal"),
                    assignee,
                    str(payload.get("node") or ""),
                    str(payload.get("agent") or assignee),
                    str(payload.get("role") or ""),
                    str(payload.get("package") or ""),
                    int(payload.get("done_ratio") if isinstance(payload.get("done_ratio"), int) else issue_done_ratio(payload_status)),
                    str(payload.get("description") or ""),
                    now,
                    now if payload_status.lower() == "done" else "",
                    str(payload.get("source") or "api"),
                    str(payload.get("dispatch") or ""),
                    str(payload.get("validation_report") or ""),
                    now,
                ),
            )
            note = parse_payload_note(payload) or "Issue created."
            conn.execute(
                """
                insert into journals(issue_id, author, created_on, notes, old_status, new_status, source)
                values (?, ?, ?, ?, ?, ?, 'api')
                """,
                (
                    issue_id,
                    assignee,
                    now,
                    note,
                    "",
                    payload_status,
                ),
            )
            sync_validation_evidence(conn, issue_id, str(payload.get("validation_report") or ""))
        return get_issue(conn, issue_id)


@app.patch("/api/issues/{issue_id}")
def api_update_issue(
    issue_id: int = FastAPIPath(ge=1),
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = payload or {}
    with get_db() as conn:
        row = conn.execute("select * from issues where id = ?", (issue_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Issue not found: {issue_id}")

        allowed = {
            "subject",
            "project",
            "tracker",
            "status",
            "priority",
            "assignee",
            "node",
            "agent",
            "role",
            "package",
            "description",
            "dispatch",
            "validation_report",
            "source",
            "done_ratio",
        }

        updates: dict[str, Any] = {key: payload[key] for key in allowed if key in payload}
        if "status" in updates:
            status = str(updates["status"]) if updates["status"] is not None else str(row["status"])
            updates["status"] = status
            updates["done_ratio"] = issue_done_ratio(status)
            updates["closed_on"] = now_iso() if status.lower() == "done" else ""

        if "done_ratio" in updates and isinstance(updates["done_ratio"], str) and updates["done_ratio"].strip().isdigit():
            updates["done_ratio"] = int(updates["done_ratio"])

    note = parse_payload_note(payload)
    now = now_iso()

    with conn:
        if updates:
            updates["updated_on"] = now
            set_clause = ", ".join(f"{key} = ?" for key in updates)
            conn.execute(f"update issues set {set_clause} where id = ?", (*updates.values(), issue_id))

        if updates or note:
            old_status = str(row["status"])
            new_status = str(updates.get("status") or row["status"])
            author = str(payload.get("author") or payload.get("agent") or payload.get("assignee") or row["assignee"] or "local operator")
            if not note:
                if "status" in updates and old_status != new_status:
                    note = f"Status changed from {old_status} to {new_status}."
                else:
                    note = "Issue updated."
            conn.execute(
                """
                insert into journals(issue_id, author, created_on, notes, old_status, new_status, source)
                values (?, ?, ?, ?, ?, ?, 'api')
                """,
                (issue_id, author, now, note, old_status, new_status),
            )
        if "validation_report" in updates:
            sync_validation_evidence(conn, issue_id, str(updates.get("validation_report") or ""))
        return get_issue(conn, issue_id)


@app.post("/api/issues/{issue_id}/notes")
def api_add_note(
    issue_id: int = FastAPIPath(ge=1),
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = payload or {}
    note = parse_payload_note(payload)
    if not note:
        raise HTTPException(status_code=400, detail="notes is required")

    with get_db() as conn:
        row = conn.execute("select status, assignee from issues where id = ?", (issue_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Issue not found: {issue_id}")

        now = now_iso()
        with conn:
            conn.execute(
                """
                insert into journals(issue_id, author, created_on, notes, old_status, new_status, source)
                values (?, ?, ?, ?, ?, ?, 'api')
                """,
                (
                    issue_id,
                    str(payload.get("author") or row["assignee"] or "local operator"),
                    now,
                    note,
                    str(row["status"]),
                    str(row["status"]),
                ),
            )
            conn.execute("update issues set updated_on = ? where id = ?", (now, issue_id))
        return get_issue(conn, issue_id)
