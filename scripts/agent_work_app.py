#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import json
import mimetypes
import os
import signal
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import webbrowser
import shlex
import shutil
from copy import deepcopy
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import urlopen


ROOT_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = ROOT_DIR / "templates" / "agent-work-app"
STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "cento"
DB_PATH = Path(os.environ.get("CENTO_AGENT_WORK_DB", STATE_DIR / "agent-work-app.sqlite3"))
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 47910
PORT_SPAN = 20
LOCAL_ID_FLOOR = int(os.environ.get("CENTO_REPLACEMENT_LOCAL_ID_FLOOR", "1000000"))

DEFAULT_PROJECT = "cento-agent-work"
DEFAULT_PROJECT_NAME = "Cento Taskstream"
DEFAULT_TRACKERS = ("Agent Task", "Agent Epic", "Feature", "Bug", "Support")
DEFAULT_STATUSES = (
    "Queued",
    "Running",
    "Review",
    "Blocked",
    "Validating",
    "Done",
)
DEFAULT_QUERY_FILTERS: list[dict[str, Any]] = [
    {"name": "Open", "filters": '{"status":"open"}', "is_default": 1},
    {"name": "All", "filters": "{}", "is_default": 0},
]
DEFAULT_CUSTOM_FIELDS = (
    ("Agent Node", "string"),
    ("Agent Owner", "string"),
    ("Agent Role", "string"),
    ("Cento Work Package", "string"),
    ("Cluster Dispatch", "text"),
    ("Validation Report", "text"),
    ("Agent State", "string"),
)
DEFAULT_ASSIGNEE_DISPLAY = "Taskstream Admin"
ISSUE_CUSTOM_FIELD_MAP = {
    "node": "Agent Node",
    "agent": "Agent Owner",
    "role": "Agent Role",
    "package": "Cento Work Package",
    "dispatch": "Cluster Dispatch",
    "validation_report": "Validation Report",
}
REFERENCE_TABLE_ISSUE_COLUMN = {
    "projects": ("project", "identifier"),
    "trackers": ("tracker", "name"),
    "statuses": ("status", "name"),
    "assignees": ("assignee", "login"),
}
PID_FILE = STATE_DIR / "agent-work-app.pid"
LOG_FILE = STATE_DIR / "agent-work-app.log"
SYNC_LOG_FILE = STATE_DIR / "agent-work-app-sync.log"
SYNC_LOCK_FILE = STATE_DIR / "agent-work-app-sync.lock"
DEV_PIPELINE_STUDIO_ROOT = ROOT_DIR / "workspace" / "runs" / "dev-pipeline-studio" / "docs-pages" / "latest"
HEALTH_PATH = "/health"
SYNC_CRON_BEGIN = "# >>> cento agent-work-app sync >>>"
SYNC_CRON_END = "# <<< cento agent-work-app sync <<<"
SYNC_SOURCE_ENV = "CENTO_AGENT_WORK_APP_SYNC_SOURCE"
SYNC_TIMEOUT_ENV = "CENTO_AGENT_WORK_APP_SYNC_TIMEOUT_SECONDS"


class AgentWorkAppError(RuntimeError):
    pass


def build_server_parent() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--open", action="store_true")
    parser.add_argument("--sync", action="store_true", help="Sync from the current agent-work CLI before serving.")
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--exact-port", action="store_true", help="Bind exactly to --port instead of scanning for a free port.")
    return parser


def parse_args() -> argparse.Namespace:
    server_parent = build_server_parent()
    parser = argparse.ArgumentParser(
        description="Run the Cento Console web app with Taskstream, Cluster, Consulting, and Docs sections.",
        parents=[server_parent],
    )
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("serve", parents=[server_parent], help="Run the app in the foreground.")
    sub.add_parser("start", parents=[server_parent], help="Start the app in the background.")
    sub.add_parser("stop", help="Stop the background app.")
    sub.add_parser("status", parents=[server_parent], help="Check the app health endpoint.")
    sub.add_parser(
        "import-redmine",
        parents=[server_parent],
        help="Import the current migration source into the local database.",
    )
    sync = sub.add_parser(
        "install-sync",
        help="Install the recurring sync cron job for the Taskstream DB used by the Cento Console app.",
    )
    sync.add_argument("--interval-minutes", type=int, default=5)
    sync.add_argument("--db", default=str(DB_PATH))
    sync.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def find_port(host: str, preferred: int) -> int:
    for port in range(preferred, preferred + PORT_SPAN):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
            except OSError:
                continue
            return port
    raise AgentWorkAppError(f"Could not bind a free port in range {preferred}-{preferred + PORT_SPAN - 1}.")


def app_url(host: str, port: int) -> str:
    return f"http://{host}:{port}/"


def health_url(host: str, port: int) -> str:
    return f"http://{host}:{port}{HEALTH_PATH}"


def read_pid_file() -> int | None:
    try:
        raw = PID_FILE.read_text().strip()
    except FileNotFoundError:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def write_pid_file(pid: int) -> None:
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(f"{pid}\n")


def remove_pid_file() -> None:
    try:
        PID_FILE.unlink()
    except FileNotFoundError:
        pass


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def pid_matches_app(pid: int) -> bool:
    if not pid_alive(pid):
        return False
    try:
        proc = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return True
    command = proc.stdout.strip()
    return "agent_work_app.py" in command or "agent-work-app" in command


def probe_health(host: str, port: int, timeout: float = 2.0) -> dict[str, Any]:
    try:
        with urlopen(health_url(host, port), timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise AgentWorkAppError(f"Health check failed with HTTP {exc.code}") from exc
    except URLError as exc:
        raise AgentWorkAppError(f"Health check failed: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise AgentWorkAppError(f"Health check returned invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise AgentWorkAppError("Health check returned a non-object payload")
    return payload


def wait_for_health(host: str, port: int, timeout: float = 20.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last_error = "unknown"
    while time.monotonic() < deadline:
        try:
            return probe_health(host, port, timeout=1.5)
        except AgentWorkAppError as exc:
            last_error = str(exc)
        time.sleep(0.25)
    raise AgentWorkAppError(f"Timed out waiting for {health_url(host, port)} to become healthy: {last_error}")


def read_log_tail(lines: int = 40) -> str:
    try:
        content = LOG_FILE.read_text()
    except FileNotFoundError:
        return ""
    return "\n".join(content.splitlines()[-lines:])


def current_crontab() -> str:
    proc = subprocess.run(["crontab", "-l"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0:
        return ""
    return proc.stdout


def sync_cron_block(interval_minutes: int, db_path: Path) -> str:
    if interval_minutes <= 0 or 60 % interval_minutes != 0:
        raise AgentWorkAppError("--interval-minutes must divide 60, for example 5, 10, 15, 20, 30, or 60")
    minute = "0" if interval_minutes == 60 else f"*/{interval_minutes}"
    command_body = (
        f"cd {shlex.quote(str(ROOT_DIR))} && "
        "python3 scripts/migrate_redmine_to_tracker.py --incremental "
        f"--db {shlex.quote(str(db_path))}"
    )
    if shutil.which("flock"):
        command = f"flock -n {shlex.quote(str(SYNC_LOCK_FILE))} bash -lc {shlex.quote(command_body)}"
    else:
        command = command_body
    return (
        f"{SYNC_CRON_BEGIN}\n"
        f"{minute} * * * * mkdir -p {shlex.quote(str(STATE_DIR))} && {command} >> {shlex.quote(str(SYNC_LOG_FILE))} 2>&1\n"
        f"{SYNC_CRON_END}\n"
    )


def strip_sync_cron_block(text: str) -> str:
    lines = text.splitlines()
    output: list[str] = []
    skipping = False
    for line in lines:
        if line.strip() == SYNC_CRON_BEGIN:
            skipping = True
            continue
        if line.strip() == SYNC_CRON_END:
            skipping = False
            continue
        if not skipping:
            output.append(line)
    return "\n".join(output).rstrip() + ("\n" if output else "")


def command_install_sync(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    new_block = sync_cron_block(args.interval_minutes, db_path)
    current = current_crontab()
    stripped = strip_sync_cron_block(current)
    updated = stripped + ("\n" if stripped.strip() else "") + new_block
    if args.dry_run:
        print(updated, end="")
        return 0
    proc = subprocess.run(["crontab", "-"], input=updated, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0:
        raise AgentWorkAppError(proc.stderr.strip() or "crontab install failed")
    print(f"installed agent-work-app sync: every {args.interval_minutes} minutes")
    print(f"db: {db_path}")
    print(f"log: {SYNC_LOG_FILE}")
    return 0


def run_server(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    with connect(db_path) as conn:
        init_db(conn)
        if args.sync:
            sync_from_agent_work(conn)
    port = args.port if args.exact_port else find_port(args.host, args.port)
    url = app_url(args.host, port)
    server = ThreadingHTTPServer((args.host, port), make_handler(db_path))
    print(f"Cento Console running at {url}")
    print(f"Database: {db_path}")
    if args.open:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Cento Console.")
    finally:
        server.server_close()
    return 0


def command_start(args: argparse.Namespace) -> int:
    try:
        probe_health(args.host, args.port)
        print(f"Cento Console is already running at {health_url(args.host, args.port)}")
        return 0
    except AgentWorkAppError:
        pass

    stale_pid = read_pid_file()
    if stale_pid is not None and not pid_matches_app(stale_pid):
        remove_pid_file()

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "serve",
        "--host",
        args.host,
        "--port",
        str(args.port),
        "--db",
        args.db,
        "--exact-port",
    ]
    if args.sync:
        command.append("--sync")
    if args.open:
        command.append("--open")

    with LOG_FILE.open("a", encoding="utf-8") as log_file:
        proc = subprocess.Popen(
            command,
            cwd=ROOT_DIR,
            stdout=log_file,
            stderr=log_file,
            start_new_session=True,
        )
    write_pid_file(proc.pid)
    try:
        wait_for_health(args.host, args.port)
    except AgentWorkAppError as exc:
        if proc.poll() is None:
            try:
                os.kill(proc.pid, signal.SIGTERM)
            except OSError:
                pass
        raise AgentWorkAppError(f"Failed to start agent-work app: {exc}\n{read_log_tail()}") from exc
    print(f"Started Cento Console at {app_url(args.host, args.port)} (pid {proc.pid})")
    return 0


def command_stop(args: argparse.Namespace) -> int:
    pid = read_pid_file()
    if pid is None:
        print("Cento Console is not running.")
        return 0
    if not pid_matches_app(pid):
        remove_pid_file()
        print(f"Removed stale PID file {PID_FILE}.")
        return 0

    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        remove_pid_file()
        print(f"Removed stale PID file {PID_FILE}.")
        return 0

    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline and pid_alive(pid):
        time.sleep(0.2)
    if pid_alive(pid):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    remove_pid_file()
    print(f"Stopped Cento Console (pid {pid}).")
    return 0


def command_status(args: argparse.Namespace) -> int:
    payload = probe_health(args.host, args.port)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def command_import_redmine(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    with connect(db_path) as conn:
        init_db(conn)
        payload = sync_from_agent_work(conn)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=120)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma busy_timeout = 120000")
    conn.execute("pragma journal_mode = WAL")
    conn.execute("pragma foreign_keys = ON")
    conn.execute("pragma synchronous = NORMAL")
    return conn


SCHEMA = """
create table if not exists issues (
  id integer primary key,
  subject text not null,
  project text not null default 'cento-agent-work',
  tracker text not null,
  status text not null,
  priority text not null default 'Normal',
  assignee text not null default 'Taskstream Admin',
  node text not null default '',
  agent text not null default '',
  role text not null default '',
  package text not null default '',
  done_ratio integer not null default 0,
  updated_on text not null,
  description text not null default '',
  source text not null default 'redmine',
  migrated_at text not null
);

create table if not exists projects (
  id integer primary key autoincrement,
  identifier text not null unique,
  name text not null,
  created_on text not null
);

create table if not exists trackers (
  id integer primary key autoincrement,
  name text not null unique,
  created_on text not null
);

create table if not exists statuses (
  id integer primary key autoincrement,
  name text not null unique,
  is_closed integer not null default 0,
  created_on text not null
);

create table if not exists assignees (
  id integer primary key autoincrement,
  login text not null unique,
  display_name text not null default '',
  created_on text not null
);

create table if not exists users (
  id integer primary key autoincrement,
  login text not null unique,
  display_name text not null default '',
  mail text not null default '',
  created_on text not null
);

create table if not exists issue_custom_fields (
  id integer primary key autoincrement,
  name text not null unique,
  field_type text not null default 'string',
  created_on text not null
);

create table if not exists custom_fields (
  id integer primary key autoincrement,
  name text not null unique,
  field_type text not null default 'string',
  created_on text not null
);

create table if not exists issue_custom_values (
  issue_id integer not null,
  custom_field_id integer not null,
  value text not null default '',
  updated_on text not null,
  primary key (issue_id, custom_field_id),
  foreign key(issue_id) references issues(id),
  foreign key(custom_field_id) references issue_custom_fields(id)
);

create table if not exists custom_values (
  issue_id integer not null,
  custom_field_id integer not null,
  value text not null default '',
  updated_on text not null,
  primary key (issue_id, custom_field_id),
  foreign key(issue_id) references issues(id),
  foreign key(custom_field_id) references custom_fields(id)
);

create table if not exists issue_entities (
  issue_id integer primary key,
  project_id integer,
  tracker_id integer,
  status_id integer,
  assignee_id integer,
  updated_on text not null,
  foreign key(issue_id) references issues(id),
  foreign key(project_id) references projects(id),
  foreign key(tracker_id) references trackers(id),
  foreign key(status_id) references statuses(id),
  foreign key(assignee_id) references assignees(id)
);

create table if not exists queries (
  id integer primary key autoincrement,
  name text not null unique,
  filters text not null default '{}',
  is_default integer not null default 0,
  created_on text not null
);

create table if not exists saved_queries (
  id integer primary key autoincrement,
  name text not null unique,
  filters text not null default '{}',
  is_default integer not null default 0,
  created_on text not null
);

create table if not exists journals (
  id integer primary key autoincrement,
  issue_id integer not null,
  author text not null default 'Taskstream Admin',
  created_on text not null,
  notes text not null,
  old_status text not null default '',
  new_status text not null default '',
  source text not null default 'migration',
  foreign key(issue_id) references issues(id)
);

create table if not exists journal_details (
  id integer primary key autoincrement,
  journal_id integer not null,
  property text not null default 'attr',
  prop_key text not null,
  old_value text not null default '',
  value text not null default '',
  foreign key(journal_id) references journals(id)
);

create table if not exists attachments (
  id integer primary key autoincrement,
  issue_id integer not null,
  filename text not null,
  size text not null default '',
  path text not null default '',
  created_on text not null,
  mime_type text not null default '',
  checksum text not null default '',
  evidence_type text not null default '',
  foreign key(issue_id) references issues(id)
);

create table if not exists validation_evidences (
  id integer primary key autoincrement,
  issue_id integer not null,
  label text not null default '',
  path text not null default '',
  url text not null default '',
  created_on text not null,
  source text not null default 'local',
  note text not null default '',
  foreign key(issue_id) references issues(id)
  unique(issue_id, path)
);

create table if not exists migration_runs (
  id integer primary key autoincrement,
  source text not null,
  started_at text not null,
  finished_at text not null,
  issue_count integer not null,
  status text not null,
  detail text not null default ''
);

create table if not exists sync_meta (
  key text primary key,
  value text not null default '',
  updated_on text not null
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"pragma table_info({table})").fetchall()}


def ensure_table_column(conn: sqlite3.Connection, table: str, name: str, ddl: str) -> None:
    if name not in table_columns(conn, table):
        conn.execute(f"alter table {table} add column {name} {ddl}")


def ensure_index(conn: sqlite3.Connection, index_name: str, table: str, ddl: str, columns: str) -> None:
    existing = {row["name"] for row in conn.execute(f"pragma index_list({table})").fetchall()}
    if index_name in existing:
        return
    conn.execute(f"create {ddl} {index_name} on {table}({columns})")


def ensure_status(conn: sqlite3.Connection, name: str, is_closed: int | None = None) -> int:
    key = str(name).strip()
    row = conn.execute("select id from statuses where lower(name) = ?", (key.lower(),)).fetchone()
    if row:
        return int(row["id"])
    now = now_iso()
    conn.execute(
        "insert into statuses(name, is_closed, created_on) values (?, ?, ?)",
        (key, int(bool(is_closed) or key.lower() == "done"), now),
    )
    return int(conn.execute("select last_insert_rowid()").fetchone()[0])


def ensure_project(conn: sqlite3.Connection, name: str, identifier: str | None = None) -> int:
    project_name = str(name).strip() or DEFAULT_PROJECT_NAME
    project_id = "project"
    project_id = "".join(ch if ch.isalnum() else "-" for ch in project_name.lower()).strip("-") or project_id
    if identifier:
        project_id = str(identifier).strip() or project_id
    row = conn.execute("select id from projects where identifier = ?", (project_id,)).fetchone()
    if row:
        return int(row["id"])
    now = now_iso()
    conn.execute("insert into projects(identifier, name, created_on) values (?, ?, ?)", (project_id, project_name, now))
    return int(conn.execute("select last_insert_rowid()").fetchone()[0])


def ensure_tracker(conn: sqlite3.Connection, name: str) -> int:
    tracker = str(name).strip() or "Agent Task"
    row = conn.execute("select id from trackers where lower(name) = ?", (tracker.lower(),)).fetchone()
    if row:
        return int(row["id"])
    now = now_iso()
    conn.execute("insert into trackers(name, created_on) values (?, ?)", (tracker, now))
    return int(conn.execute("select last_insert_rowid()").fetchone()[0])


def ensure_assignee(conn: sqlite3.Connection, login: str) -> int:
    username = str(login).strip() or DEFAULT_ASSIGNEE_DISPLAY
    row = conn.execute("select id from assignees where lower(login) = ?", (username.lower(),)).fetchone()
    if row:
        conn.execute(
            "insert or ignore into users(id, login, display_name, created_on) values (?, ?, ?, ?)",
            (int(row["id"]), username, username, now_iso()),
        )
        return int(row["id"])
    now = now_iso()
    conn.execute("insert into assignees(login, display_name, created_on) values (?, ?, ?)", (username, username, now))
    assignee_id = int(conn.execute("select last_insert_rowid()").fetchone()[0])
    conn.execute(
        "insert or ignore into users(id, login, display_name, created_on) values (?, ?, ?, ?)",
        (assignee_id, username, username, now),
    )
    return assignee_id


def ensure_custom_field(conn: sqlite3.Connection, name: str, field_type: str = "string") -> int:
    field_name = str(name).strip()
    row = conn.execute("select id from issue_custom_fields where name = ?", (field_name,)).fetchone()
    if row:
        conn.execute(
            "insert or ignore into custom_fields(id, name, field_type, created_on) values (?, ?, ?, ?)",
            (int(row["id"]), field_name, field_type, now_iso()),
        )
        return int(row["id"])
    now = now_iso()
    conn.execute(
        "insert into issue_custom_fields(name, field_type, created_on) values (?, ?, ?)",
        (field_name, field_type, now),
    )
    field_id = int(conn.execute("select last_insert_rowid()").fetchone()[0])
    conn.execute(
        "insert or ignore into custom_fields(id, name, field_type, created_on) values (?, ?, ?, ?)",
        (field_id, field_name, field_type, now),
    )
    return field_id


def ensure_query(conn: sqlite3.Connection, name: str, filters: str, is_default: int = 0) -> int:
    name = str(name).strip()
    row = conn.execute("select id from queries where name = ?", (name,)).fetchone()
    if row:
        conn.execute(
            "insert or ignore into saved_queries(id, name, filters, is_default, created_on) values (?, ?, ?, ?, ?)",
            (int(row["id"]), name, filters, int(is_default), now_iso()),
        )
        return int(row["id"])
    now = now_iso()
    conn.execute(
        "insert into queries(name, filters, is_default, created_on) values (?, ?, ?, ?)",
        (name, filters, int(is_default), now),
    )
    query_id = int(conn.execute("select last_insert_rowid()").fetchone()[0])
    conn.execute(
        "insert or ignore into saved_queries(id, name, filters, is_default, created_on) values (?, ?, ?, ?, ?)",
        (query_id, name, filters, int(is_default), now),
    )
    return query_id


def ensure_issue_entity_links(
    conn: sqlite3.Connection,
    issue_id: int,
    *,
    project: str | None = None,
    tracker: str | None = None,
    status: str | None = None,
    assignee: str | None = None,
) -> None:
    now = now_iso()
    project_id = ensure_project(conn, project or DEFAULT_PROJECT, DEFAULT_PROJECT)
    tracker_id = ensure_tracker(conn, tracker or "Agent Task")
    status_id = ensure_status(conn, status or "Queued")
    assignee_id = ensure_assignee(conn, assignee or DEFAULT_ASSIGNEE_DISPLAY)
    conn.execute(
        """
        insert into issue_entities(issue_id, project_id, tracker_id, status_id, assignee_id, updated_on)
        values (?, ?, ?, ?, ?, ?)
        on conflict(issue_id) do update set
          project_id = excluded.project_id,
          tracker_id = excluded.tracker_id,
          status_id = excluded.status_id,
          assignee_id = excluded.assignee_id,
          updated_on = excluded.updated_on
        """,
        (issue_id, project_id, tracker_id, status_id, assignee_id, now),
    )


def upsert_issue_custom_values(conn: sqlite3.Connection, issue_id: int, custom_values: dict[str, Any]) -> None:
    now = now_iso()
    for key, value in custom_values.items():
        if value is None:
            continue
        field_id = ensure_custom_field(conn, key)
        conn.execute(
            """
            insert into issue_custom_values(issue_id, custom_field_id, value, updated_on)
            values (?, ?, ?, ?)
            on conflict(issue_id, custom_field_id) do update set
              value = excluded.value,
              updated_on = excluded.updated_on
            """,
            (issue_id, field_id, str(value), now),
        )
        conn.execute(
            """
            insert into custom_values(issue_id, custom_field_id, value, updated_on)
            values (?, ?, ?, ?)
            on conflict(issue_id, custom_field_id) do update set
              value = excluded.value,
              updated_on = excluded.updated_on
            """,
            (issue_id, field_id, str(value), now),
        )


def issue_custom_fields_payload(payload: dict[str, Any]) -> dict[str, str]:
    values: dict[str, str] = {}
    for key, field_name in ISSUE_CUSTOM_FIELD_MAP.items():
        if key in payload and payload.get(key) is not None:
            values[field_name] = str(payload[key])
    custom_values = payload.get("custom_fields")
    if isinstance(custom_values, dict):
        for key, value in custom_values.items():
            values[str(key)] = str(value)
    return values


def issue_custom_fields_for_issue(conn: sqlite3.Connection, issue_id: int) -> dict[str, str]:
    fields = {}
    for row in conn.execute(
        """
        select icf.name, coalesce(icv.value, '') as value
        from issue_custom_fields icf
        left join issue_custom_values icv on icv.custom_field_id = icf.id and icv.issue_id = ?
        order by icf.name
        """,
        (issue_id,),
    ):
        fields[str(row["name"])] = str(row["value"])
    return fields


def add_validation_evidence(
    conn: sqlite3.Connection,
    issue_id: int,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if not conn.execute("select 1 from issues where id = ?", (issue_id,)).fetchone():
        raise AgentWorkAppError(f"Issue not found: {issue_id}")
    path = str(payload.get("path") or "").strip()
    url = str(payload.get("url") or "").strip()
    label = str(payload.get("label") or "").strip()
    if not path and not url:
        raise AgentWorkAppError("path or url is required")
    now = now_iso()
    with conn:
        if not path:
            path = f"validation://{issue_id}/{now_iso()}"
        existing = conn.execute(
            "select 1 from validation_evidences where issue_id = ? and path = ?",
            (issue_id, path),
        ).fetchone()
        if existing:
            conn.execute(
                """
                update validation_evidences
                set label = ?, url = ?, source = ?, note = ?, created_on = ?
                where issue_id = ? and path = ?
                """,
                (
                    label,
                    url,
                    str(payload.get("source") or "local"),
                    str(payload.get("note") or ""),
                    now,
                    issue_id,
                    path,
                ),
            )
        else:
            conn.execute(
                "insert into validation_evidences(issue_id, label, path, url, created_on, source, note) values (?, ?, ?, ?, ?, ?, ?)",
                (
                    issue_id,
                    label,
                    path,
                    url,
                    now,
                    str(payload.get("source") or "local"),
                    str(payload.get("note") or ""),
                ),
            )
    return issue_detail(conn, issue_id)


def issue_validation_evidences(conn: sqlite3.Connection, issue_id: int) -> list[dict[str, Any]]:
    return [
        row_dict(row)
        for row in conn.execute(
            "select * from validation_evidences where issue_id = ? order by datetime(created_on) desc, id desc",
            (issue_id,),
        )
    ]


def issue_filter_from_raw(payload: dict[str, Any] | None) -> dict[str, Any]:
    filters: dict[str, Any] = {}
    if not isinstance(payload, dict):
        return filters
    status = payload.get("status")
    if status is not None:
        filters["status"] = str(status)
    for key in ("project", "tracker", "assignee"):
        if key in payload and payload.get(key) is not None:
            filters[key] = str(payload.get(key))
    return filters


def filter_clause(filters: dict[str, Any]) -> tuple[str, list[Any]]:
    where = []
    params: list[Any] = []
    if status := filters.get("status"):
        if str(status).lower() == "open":
            where.append("lower(status) != 'done'")
        elif str(status).lower() == "all":
            pass
        else:
            where.append("lower(status) = ?")
            params.append(str(status).lower())
    for key in ("project", "tracker", "assignee", "node", "agent", "role", "package"):
        value = filters.get(key)
        if value:
            where.append(f"lower({key}) = ?")
            params.append(str(value).lower())
    where_clause = f"where {' and '.join(where)}" if where else ""
    return where_clause, params


def list_queries(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = []
    for row in conn.execute("select id, name, filters, is_default, created_on from queries order by id"):
        rows.append(row_dict(row))
    return rows


def list_reference(conn: sqlite3.Connection, table: str, include_counts: bool = False) -> list[dict[str, Any]]:
    rows = []
    for row in conn.execute(f"select * from {table} order by id"):
        item = row_dict(row)
        if include_counts:
            mapping = REFERENCE_TABLE_ISSUE_COLUMN.get(table)
            if mapping:
                issue_column, value_key = mapping
                value = item.get(value_key) or ""
                item["issue_count"] = conn.execute(
                    f"select count(*) from issues where {issue_column} = ?",
                    (str(value),),
                ).fetchone()[0]
        rows.append(item)
    return rows


def seed_defaults(conn: sqlite3.Connection) -> None:
    for tracker in DEFAULT_TRACKERS:
        ensure_tracker(conn, tracker)
    for status in DEFAULT_STATUSES:
        ensure_status(conn, status)
    for field, field_type in DEFAULT_CUSTOM_FIELDS:
        ensure_custom_field(conn, field, field_type)
    ensure_project(conn, DEFAULT_PROJECT_NAME, DEFAULT_PROJECT)
    for query in DEFAULT_QUERY_FILTERS:
        ensure_query(conn, query["name"], query["filters"], query["is_default"])
    ensure_assignee(conn, DEFAULT_ASSIGNEE_DISPLAY)


def next_local_issue_id(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "select coalesce(max(id), ? - 1) + 1 as next_id from issues where id >= ?",
        (LOCAL_ID_FLOOR, LOCAL_ID_FLOOR),
    ).fetchone()
    return int(row["next_id"]) if row else LOCAL_ID_FLOOR


def relocate_local_issue(conn: sqlite3.Connection, issue_id: int) -> int:
    new_id = next_local_issue_id(conn)
    for table in (
        "attachments",
        "custom_values",
        "issue_custom_values",
        "issue_entities",
        "journals",
        "validation_evidences",
    ):
        conn.execute(f"update {table} set issue_id = ? where issue_id = ?", (new_id, issue_id))
    conn.execute("update issues set id = ? where id = ?", (new_id, issue_id))
    return new_id


def reserve_redmine_issue_id(conn: sqlite3.Connection, issue_id: int) -> None:
    row = conn.execute("select source from issues where id = ?", (issue_id,)).fetchone()
    if row and str(row["source"] or "") == "replacement":
        relocate_local_issue(conn, issue_id)


def relocate_low_local_issues(conn: sqlite3.Connection) -> int:
    rows = list(
        conn.execute(
            "select id from issues where source = 'replacement' and id < ? order by id",
            (LOCAL_ID_FLOOR,),
        )
    )
    for row in rows:
        relocate_local_issue(conn, int(row["id"]))
    return len(rows)


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    ensure_table_column(conn, "attachments", "mime_type", "text not null default ''")
    ensure_table_column(conn, "attachments", "checksum", "text not null default ''")
    ensure_table_column(conn, "attachments", "evidence_type", "text not null default ''")
    ensure_table_column(conn, "issues", "project", "text not null default 'cento-agent-work'")
    ensure_table_column(conn, "issues", "tracker", "text not null default 'Agent Task'")
    ensure_table_column(conn, "issues", "status", "text not null default 'Queued'")
    ensure_table_column(conn, "issues", "priority", "text not null default 'Normal'")
    ensure_table_column(conn, "issues", "assignee", f"text not null default '{DEFAULT_ASSIGNEE_DISPLAY}'")
    ensure_table_column(conn, "issues", "node", "text not null default ''")
    ensure_table_column(conn, "issues", "agent", "text not null default ''")
    ensure_table_column(conn, "issues", "role", "text not null default 'builder'")
    ensure_table_column(conn, "issues", "package", "text not null default 'default'")
    ensure_table_column(conn, "issues", "done_ratio", "integer not null default 0")
    ensure_table_column(conn, "issues", "description", "text not null default ''")
    ensure_table_column(conn, "issues", "closed_on", "text not null default ''")
    ensure_table_column(conn, "issues", "dispatch", "text not null default ''")
    ensure_table_column(conn, "issues", "validation_report", "text not null default ''")
    ensure_index(
        conn,
        "ux_validation_evidences_issue_path",
        "validation_evidences",
        "unique index",
        "issue_id, path",
    )
    seed_defaults(conn)
    conn.commit()


def run_agent_work_json(*args: str, timeout: int = 20, backend: str | None = None) -> dict[str, Any]:
    command = ["python3", str(ROOT_DIR / "scripts" / "agent_work.py"), *args]
    env = os.environ.copy()
    if backend:
        env["CENTO_AGENT_WORK_BACKEND"] = backend
    result = subprocess.run(command, cwd=ROOT_DIR, env=env, capture_output=True, text=True, timeout=timeout, check=False)
    if result.returncode != 0:
        raise AgentWorkAppError(result.stderr.strip() or result.stdout.strip() or f"agent_work.py exited {result.returncode}")
    payload = json.loads(result.stdout)
    return payload if isinstance(payload, dict) else {}


def run_list() -> dict[str, Any]:
    try:
        payload = run_agent_work_json("runs", "--json", "--active")
    except Exception as exc:
        return {"runs": [], "count": 0, "error": str(exc)}
    runs = payload.get("runs") or []
    live = []
    stale = []
    by_pool: dict[str, int] = {"builder": 0, "validator": 0, "small": 0, "coordinator": 0}
    for item in runs:
        status = str(item.get("status") or "")
        health = str(item.get("health") or "")
        is_live = status in {"planned", "launching", "running", "untracked_interactive"} and (
            bool(item.get("pid_alive")) or bool(item.get("tmux_alive")) or status == "untracked_interactive"
        )
        (live if is_live else stale).append(item)
        if not is_live:
            continue
        agent = str(item.get("agent") or "")
        role = str(item.get("role") or "")
        if agent.startswith("small-worker"):
            by_pool["small"] += 1
        elif role in by_pool:
            by_pool[role] += 1
        elif health == "running":
            by_pool["builder"] += 1
    payload["runs"] = runs
    payload["count"] = len(runs)
    manager_summary: dict[str, Any] = {}
    try:
        manager = subprocess.run(
            [sys.executable, str(ROOT_DIR / "scripts" / "agent_manager.py"), "scan", "--json"],
            cwd=ROOT_DIR,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
        )
        if manager.returncode == 0:
            manager_payload = json.loads(manager.stdout)
            if isinstance(manager_payload, dict) and isinstance(manager_payload.get("summary"), dict):
                manager_summary = manager_payload["summary"]
    except Exception:
        manager_summary = {}
    payload["summary"] = {
        "live": len(live),
        "stale": len(stale),
        "actionable_stale": int(manager_summary.get("actionable_stale", len(stale)) or 0),
        "historical_stale": int(manager_summary.get("historical_stale", 0) or 0),
        "archived": int(manager_summary.get("archived", 0) or 0),
        "manual": int(manager_summary.get("manual", 0) or 0),
        "risk_count": int(manager_summary.get("risk_count", 0) or 0),
        "by_pool": by_pool,
        "targets": {"builder": 4, "validator": 3, "small": 3, "coordinator": 1},
    }
    return payload


def read_json_path(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def write_json_path(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def title_status(value: str, fallback: str = "") -> str:
    raw = str(value or fallback or "").strip()
    if not raw:
        return ""
    return raw.replace("_", " ").replace("-", " ").title()


def event_count(path: Path) -> int:
    try:
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    except OSError:
        return 0


def dev_pipeline_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT_DIR.resolve()))
    except ValueError:
        return str(path)


def dev_pipeline_root_path(root: Path, relative: str) -> Path:
    clean = str(relative or "").strip().lstrip("/")
    if not clean:
        raise AgentWorkAppError("pipeline artifact path is required")
    path = (root / clean).resolve()
    root_resolved = root.resolve()
    if path != root_resolved and root_resolved not in path.parents:
        raise AgentWorkAppError("pipeline artifact path is outside the studio root")
    return path


def dev_pipeline_slug(value: str, fallback: str) -> str:
    raw = str(value or fallback or "").strip().lower()
    chars: list[str] = []
    previous_dash = False
    for char in raw:
        if char.isalnum():
            chars.append(char)
            previous_dash = False
        elif not previous_dash:
            chars.append("-")
            previous_dash = True
    slug = "".join(chars).strip("-")
    return slug or fallback


def dev_pipeline_unique_id(items: list[dict[str, Any]], base_id: str) -> str:
    existing = {str(item.get("id") or "") for item in items}
    candidate = base_id
    index = 2
    while candidate in existing:
        candidate = f"{base_id}-{index}"
        index += 1
    return candidate


def dev_pipeline_text(value: Any, current: str = "") -> str:
    if value is None:
        return current
    return str(value).strip()


def dev_pipeline_float(value: Any, current: float) -> float:
    if value is None or value == "":
        return current
    try:
        return float(value)
    except (TypeError, ValueError):
        return current


def dev_pipeline_text_list(value: Any, current: list[str]) -> list[str]:
    if value is None:
        return current
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [line.strip() for line in str(value).splitlines() if line.strip()]


DEV_PIPELINE_INPUT_TYPES = {"text", "details", "image", "questionnaire", "path", "evidence"}


def dev_pipeline_input_type(value: Any, fallback: str = "text") -> str:
    raw = dev_pipeline_text(value, fallback) or fallback
    kind = raw.lower().replace("_", "-").replace(" ", "-")
    aliases = {
        "detail": "details",
        "images": "image",
        "screenshot": "image",
        "mockup": "image",
        "questions": "questionnaire",
        "question": "questionnaire",
        "form": "questionnaire",
        "paths": "path",
        "route": "path",
        "routes": "path",
        "command": "path",
        "artifact": "evidence",
        "artifacts": "evidence",
        "receipt": "evidence",
    }
    kind = aliases.get(kind, kind)
    if kind in DEV_PIPELINE_INPUT_TYPES:
        return kind
    return fallback if fallback in DEV_PIPELINE_INPUT_TYPES else "text"


def dev_pipeline_inferred_input_type(input_id: str, title: str) -> str:
    text = f"{input_id} {title}".lower()
    if any(token in text for token in ("image", "screenshot", "mockup", "visual", "reference")):
        return "image"
    if any(token in text for token in ("questionnaire", "question", "acceptance", "criteria")):
        return "questionnaire"
    if any(token in text for token in ("path", "surface", "route", "command", "file")):
        return "path"
    if any(token in text for token in ("evidence", "receipt", "artifact", "validation")):
        return "evidence"
    if any(token in text for token in ("detail", "brief", "objective", "constraint")):
        return "details"
    return "text"


def dev_pipeline_question_items(value: Any, current: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    raw_items = value if isinstance(value, list) else current if isinstance(current, list) else []
    questions: list[dict[str, Any]] = []
    for index, item in enumerate(raw_items, start=1):
        if isinstance(item, str):
            prompt = item.strip()
            source: dict[str, Any] = {}
        elif isinstance(item, dict):
            source = item
            prompt = dev_pipeline_text(item.get("prompt", item.get("question")), "")
        else:
            continue
        if not prompt:
            continue
        options = source.get("options") if isinstance(source, dict) else []
        questions.append(
            {
                "id": dev_pipeline_slug(dev_pipeline_text(source.get("id") if isinstance(source, dict) else "", f"q-{index}"), f"q-{index}"),
                "prompt": prompt,
                "required": bool(source.get("required", True)) if isinstance(source, dict) else True,
                "answer_type": dev_pipeline_text(source.get("answer_type", source.get("type")) if isinstance(source, dict) else "", "text"),
                "options": dev_pipeline_text_list(options, []),
            }
        )
    return questions


def dev_pipeline_required_inputs(value: Any, current: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    raw_items = value if isinstance(value, list) else current if isinstance(current, list) else []
    inputs: list[dict[str, Any]] = []
    for index, item in enumerate(raw_items, start=1):
        if not isinstance(item, dict):
            continue
        title = dev_pipeline_text(item.get("title"), "")
        if not title:
            continue
        status = dev_pipeline_text(item.get("status"), "Missing").lower().replace("_", "-")
        if status not in {"provided", "configured", "missing", "optional"}:
            status = "missing"
        item_id = dev_pipeline_slug(dev_pipeline_text(item.get("id"), title), f"input-{index}")
        kind = dev_pipeline_input_type(item.get("kind", item.get("input_type", item.get("type"))), dev_pipeline_inferred_input_type(item_id, title))
        normalized = {
            "id": item_id,
            "title": title,
            "detail": dev_pipeline_text(item.get("detail"), ""),
            "kind": kind,
            "input_type": kind,
            "format": dev_pipeline_text(item.get("format"), ""),
            "status": status,
            "required": bool(item.get("required", status != "optional")),
            "image_refs": dev_pipeline_text_list(item.get("image_refs", item.get("images", item.get("references"))), []),
            "image_notes": dev_pipeline_text(item.get("image_notes", item.get("reference_notes")), ""),
            "questions": dev_pipeline_question_items(item.get("questions", item.get("questionnaire"))),
            "paths": dev_pipeline_text_list(item.get("paths", item.get("target_paths", item.get("routes"))), []),
            "path_policy": dev_pipeline_text(item.get("path_policy", item.get("ownership_policy")), ""),
            "artifacts": dev_pipeline_text_list(item.get("artifacts", item.get("evidence_artifacts")), []),
            "evidence_policy": dev_pipeline_text(item.get("evidence_policy", item.get("validation_policy")), ""),
            "answer": dev_pipeline_text(item.get("answer", item.get("provided_answer", item.get("value"))), ""),
            "answer_values": dev_pipeline_text_list(item.get("answer_values", item.get("provided_values", item.get("provided_paths"))), []),
            "answer_notes": dev_pipeline_text(item.get("answer_notes", item.get("provided_notes")), ""),
            "provided_at": dev_pipeline_text(item.get("provided_at"), ""),
            "manifest": dev_pipeline_text(item.get("manifest"), ""),
        }
        normalized["answer_present"] = bool(
            str(normalized["answer"]).strip()
            or normalized["answer_values"]
            or str(normalized["answer_notes"]).strip()
            or bool(item.get("answer_present", False))
        )
        if not normalized["format"]:
            normalized["format"] = {
                "text": "plain text",
                "details": "markdown",
                "image": "image reference list",
                "questionnaire": "structured answers",
                "path": "path list",
                "evidence": "artifact list",
            }.get(kind, "plain text")
        inputs.append(normalized)
    return inputs


def dev_pipeline_validation_status(value: Any, current: str = "configured") -> str:
    status = dev_pipeline_text(value, current).lower().replace("_", "-").replace(" ", "-")
    if status not in {"passed", "configured", "queued", "warning", "failed", "manual-review"}:
        status = current if current in {"passed", "configured", "queued", "warning", "failed", "manual-review"} else "configured"
    return status


def dev_pipeline_integration_status(value: Any, current: str = "accepted") -> str:
    status = dev_pipeline_text(value, current).lower().replace("_", "-").replace(" ", "-")
    if status not in {"accepted", "configured", "queued", "merged", "blocked", "rejected"}:
        status = current if current in {"accepted", "configured", "queued", "merged", "blocked", "rejected"} else "configured"
    return status


def dev_pipeline_integration_mode(value: Any = "") -> str:
    mode = dev_pipeline_text(value, "sequential").lower().replace("_", "-").replace(" ", "-")
    if mode in {"sequential", "dependency-order", "deterministic", "batch", "manual-gate"}:
        return mode
    return "dependency-order"


def dev_pipeline_integration_gate_from_check(check: dict[str, Any]) -> str:
    name = dev_pipeline_text(check.get("name"), "").lower().replace("_", "-")
    status = dev_pipeline_text(check.get("status"), "passed").lower().replace("_", "-")
    details = dev_pipeline_text(check.get("details"), "")
    gate_map = {
        "acceptance-criteria": "Acceptance criteria are captured",
        "deterministic-checks": "Deterministic validation checks are declared",
        "handoff-complete": "Handoff evidence is complete",
        "no-owned-path-overlap": "No owned-path overlap",
        "owned-path": "Owned path receipt recorded",
        "plan-integration-receipt-accepted": "Plan integration receipt accepted",
        "plan-scope": "Implementation plan scope is accepted",
        "read-paths-indexed": "Cento context and read paths are indexed",
        "rollback-plan-recorded": "Rollback plan recorded",
        "schema": "Schema receipt recorded",
    }
    gate = gate_map.get(name, "")
    if not gate:
        if details and "workspace/runs/" not in details and not details.endswith(".json"):
            gate = details
        elif name:
            gate = name.replace("-", " ").title()
        else:
            gate = "Receipt check recorded"
    if status not in {"passed", "accepted"}:
        gate = f"{gate} ({status})"
    return gate


def dev_pipeline_integration_config(
    root: Path,
    project: dict[str, Any],
    template: dict[str, Any],
    worker: dict[str, Any],
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    worker_id = dev_pipeline_slug(dev_pipeline_text((payload or {}).get("id"), str(worker.get("id") or "")), "integration")
    receipt_rel = dev_pipeline_text((payload or {}).get("receipt"), str(worker.get("integration_receipt") or f"integration_receipts/{template.get('id')}_{worker_id}.json"))
    config_rel = dev_pipeline_text((payload or {}).get("config_path"), str(worker.get("integration_config") or f"integration/configs/{worker_id}.json"))
    receipt = dev_pipeline_artifact_json(root, receipt_rel)
    existing_config = dev_pipeline_artifact_json(root, config_rel)
    current = existing_config if existing_config else {}
    source = payload if isinstance(payload, dict) else current
    title = dev_pipeline_text(source.get("title"), f"Integrate: {worker.get('file') or f'{worker_id}.json'}")
    status = dev_pipeline_integration_status(source.get("status"), str(current.get("status") or receipt.get("status") or "accepted"))
    dependencies = dev_pipeline_text_list(source.get("dependencies"), [str(value) for value in worker.get("dependencies", []) if isinstance(value, str)])
    artifacts = dev_pipeline_text_list(source.get("artifacts"), [str(item) for item in receipt.get("changed_files", []) if isinstance(item, str)])
    if not artifacts:
        artifacts = [f"{project.get('owned_root') or 'workspace/runs/generic-task/outputs'}/{worker.get('file') or f'{worker_id}.json'}"]
    receipt_gates = [dev_pipeline_integration_gate_from_check(item) for item in receipt.get("checks", []) if isinstance(item, dict)]
    gates = dev_pipeline_text_list(source.get("gates"), [item for item in receipt_gates if item])
    if not gates:
        gates = ["Dependencies integrated first", "No owned-path conflict", "Receipt written before validation starts"]
    rollback_plan = dev_pipeline_text_list(source.get("rollback_plan"), [str(item) for item in current.get("rollback_plan", []) if isinstance(item, str)])
    if not rollback_plan:
        rollback_plan = ["Leave previous receipt untouched until apply succeeds", "Reject this integration step and preserve worker artifact for retry"]
    if dependencies:
        default_apply_policy = f"Apply this worker artifact after {', '.join(dependencies)} integration receipt{'s are' if len(dependencies) != 1 else ' is'} accepted"
    else:
        default_apply_policy = "Apply this worker artifact after pipeline and workset manifests are valid"
    return {
        "schema_version": "cento.integration_config.v1",
        "id": worker_id,
        "project": str(project.get("id") or ""),
        "template_id": str(template.get("id") or ""),
        "title": title,
        "worker_file": str(worker.get("file") or f"{worker_id}.json"),
        "status": status,
        "mode": dev_pipeline_integration_mode(source.get("mode", current.get("mode", ""))),
        "apply_policy": dev_pipeline_text(source.get("apply_policy"), str(current.get("apply_policy") or default_apply_policy)),
        "conflict_policy": dev_pipeline_text(source.get("conflict_policy"), str(current.get("conflict_policy") or "Block on overlapping owned paths, rejected dependency receipts, or a missing rollback plan")),
        "dependencies": dependencies,
        "artifacts": artifacts,
        "gates": gates,
        "rollback_plan": rollback_plan,
        "receipt": receipt_rel,
        "config_path": config_rel,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def dev_pipeline_write_integration_outputs(root: Path, manifest: dict[str, Any], project: dict[str, Any], template: dict[str, Any], config: dict[str, Any]) -> None:
    worker_id = str(config.get("id") or "integration")
    workers = [item for item in template.get("workers", []) if isinstance(item, dict)]
    worker = next((item for item in workers if str(item.get("id") or "") == worker_id), None)
    if worker is None:
        worker = {"id": worker_id, "file": str(config.get("worker_file") or f"{worker_id}.json")}
        workers.append(worker)
        template["workers"] = workers
    worker["integration_config"] = str(config.get("config_path") or f"integration/configs/{worker_id}.json")
    worker["integration_receipt"] = str(config.get("receipt") or f"integration_receipts/{template.get('id')}_{worker_id}.json")
    worker["dependencies"] = [str(value) for value in config.get("dependencies", []) if isinstance(value, str)]
    write_json_path(dev_pipeline_root_path(root, str(worker["integration_config"])), config)

    receipt_payload = {
        "schema_version": "cento.integration_receipt.v1",
        "manifest_id": str(manifest.get("id") or ""),
        "worker_id": worker_id,
        "template_id": str(template.get("id") or ""),
        "status": str(config.get("status") or "configured"),
        "mode": str(config.get("mode") or "dependency-order"),
        "apply_policy": str(config.get("apply_policy") or ""),
        "conflict_policy": str(config.get("conflict_policy") or ""),
        "dependencies": [str(value) for value in config.get("dependencies", []) if isinstance(value, str)],
        "changed_files": [str(value) for value in config.get("artifacts", []) if isinstance(value, str)],
        "checks": [
            {"name": dev_pipeline_slug(value, f"gate-{index}"), "status": "passed", "details": value}
            for index, value in enumerate([str(item) for item in config.get("gates", []) if isinstance(item, str)], start=1)
        ],
        "rollback_plan": [str(value) for value in config.get("rollback_plan", []) if isinstance(value, str)],
        "config": str(worker["integration_config"]),
        "written_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json_path(dev_pipeline_root_path(root, str(worker["integration_receipt"])), receipt_payload)

    lane_steps: list[dict[str, Any]] = []
    for item in workers:
        item_config = dev_pipeline_integration_config(root, project, template, item)
        lane_steps.append(
            {
                "id": str(item_config.get("id") or ""),
                "title": str(item_config.get("title") or ""),
                "mode": str(item_config.get("mode") or ""),
                "status": str(item_config.get("status") or ""),
                "dependencies": [str(value) for value in item_config.get("dependencies", []) if isinstance(value, str)],
                "artifacts": [str(value) for value in item_config.get("artifacts", []) if isinstance(value, str)],
                "gates": [str(value) for value in item_config.get("gates", []) if isinstance(value, str)],
                "rollback_plan": [str(value) for value in item_config.get("rollback_plan", []) if isinstance(value, str)],
                "config": str(item_config.get("config_path") or ""),
                "receipt": str(item_config.get("receipt") or ""),
            }
        )
    lane_status = "configured"
    statuses = [str(item.get("status") or "") for item in lane_steps]
    if any(status in {"blocked", "rejected"} for status in statuses):
        lane_status = "blocked"
    elif statuses and all(status in {"accepted", "merged"} for status in statuses):
        lane_status = "accepted"
    integration_lane = {
        "schema_version": "cento.integration_lane.v1",
        "id": f"{template.get('id') or 'pipeline'}-integration-lane",
        "project": str(project.get("id") or ""),
        "template_id": str(template.get("id") or ""),
        "mode": "dependency-ordered-apply",
        "status": lane_status,
        "apply_policy": "Integrate worker artifacts after declared dependencies and before validation validators run",
        "conflict_policy": "Block on overlapping owned paths, rejected receipts, or missing dependency outputs",
        "steps": lane_steps,
        "written_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json_path(dev_pipeline_root_path(root, "integration/integration_lane.json"), integration_lane)


def dev_pipeline_write_factory_step_outputs(root: Path, manifest: dict[str, Any], project: dict[str, Any], template: dict[str, Any], config: dict[str, Any]) -> None:
    step_id = str(config.get("id") or "factory-step")
    factory_steps = [item for item in template.get("factory_steps", []) if isinstance(item, dict)]
    step = next((item for item in factory_steps if str(item.get("id") or "") == step_id), None)
    if step is None:
        step = {"id": step_id, "title": str(config.get("title") or step_id), "file": str(config.get("worker_file") or f"{step_id}.json")}
        factory_steps.append(step)
        template["factory_steps"] = factory_steps
    step["title"] = str(config.get("title") or step.get("title") or step_id)
    step["file"] = str(config.get("worker_file") or step.get("file") or f"{step_id}.json")
    step["status"] = str(config.get("status") or step.get("status") or "configured")
    step["mode"] = str(config.get("mode") or "dependency-order")
    step["integration_config"] = str(config.get("config_path") or f"integration/configs/{step_id}.json")
    step["integration_receipt"] = str(config.get("receipt") or f"integration_receipts/{template.get('id')}_{step_id}.json")
    step["dependencies"] = [str(value) for value in config.get("dependencies", []) if isinstance(value, str)]
    step["artifacts"] = [str(value) for value in config.get("artifacts", []) if isinstance(value, str)]
    step["gates"] = [str(value) for value in config.get("gates", []) if isinstance(value, str)]
    step["rollback_plan"] = [str(value) for value in config.get("rollback_plan", []) if isinstance(value, str)]
    write_json_path(dev_pipeline_root_path(root, str(step["integration_config"])), config)

    receipt_payload = {
        "schema_version": "cento.factory_step_receipt.v1",
        "manifest_id": str(manifest.get("id") or ""),
        "step_id": step_id,
        "template_id": str(template.get("id") or ""),
        "project": str(project.get("id") or ""),
        "status": str(config.get("status") or "configured"),
        "mode": str(config.get("mode") or "dependency-order"),
        "apply_policy": str(config.get("apply_policy") or ""),
        "conflict_policy": str(config.get("conflict_policy") or ""),
        "dependencies": [str(value) for value in config.get("dependencies", []) if isinstance(value, str)],
        "artifacts": [str(value) for value in config.get("artifacts", []) if isinstance(value, str)],
        "checks": [
            {"name": dev_pipeline_slug(value, f"gate-{index}"), "status": "passed", "details": value}
            for index, value in enumerate([str(item) for item in config.get("gates", []) if isinstance(item, str)], start=1)
        ],
        "rollback_plan": [str(value) for value in config.get("rollback_plan", []) if isinstance(value, str)],
        "config": str(step["integration_config"]),
        "written_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json_path(dev_pipeline_root_path(root, str(step["integration_receipt"])), receipt_payload)

    execution_manifest_rel = str(template.get("execution_manifest") or "execution/execution_manifest.json")
    execution_manifest = {
        "schema_version": "cento.execution_manifest.v1",
        "manifest_id": str(manifest.get("id") or ""),
        "project": str(project.get("id") or ""),
        "template_id": str(template.get("id") or ""),
        "rollback_on_failure": True,
        "max_changed_files": 8,
        "steps": [
            {
                "id": str(item.get("id") or ""),
                "title": str(item.get("title") or item.get("id") or ""),
                "file": str(item.get("file") or ""),
                "status": str(item.get("status") or ""),
                "dependencies": [str(value) for value in item.get("dependencies", []) if isinstance(value, str)],
                "config": str(item.get("integration_config") or ""),
                "receipt": str(item.get("integration_receipt") or ""),
            }
            for item in factory_steps
        ],
        "written_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json_path(dev_pipeline_root_path(root, execution_manifest_rel), execution_manifest)


def dev_pipeline_default_validation_commands(validator_id: str) -> list[str]:
    if validator_id in {"smoke", "smoke-plus"}:
        return [
            "python3 -m json.tool workspace/runs/dev-pipeline-studio/docs-pages/latest/pipeline_manifest.json",
            "node --check templates/agent-work-app/app.js",
            "curl -fsS http://127.0.0.1:47910/api/dev-pipeline-studio?project=generic-easy-medium-task\\&template=generic-task",
        ]
    if validator_id in {"contract", "schema"}:
        return [
            "python3 -m json.tool workspace/runs/dev-pipeline-studio/docs-pages/latest/workset.json",
            "python3 -m json.tool workspace/runs/dev-pipeline-studio/docs-pages/latest/pipeline_manifest.json",
        ]
    if validator_id in {"screenshot", "evidence"}:
        return [
            "npx --yes playwright screenshot http://127.0.0.1:47910/dev-pipeline-studio workspace/runs/agent-work/dev-pipeline-studio-validation-config/validation-inspector.png",
        ]
    return []


def dev_pipeline_validator_mode(validator_id: str, value: Any = "") -> str:
    mode = dev_pipeline_text(value, "").lower().replace("_", "-").replace(" ", "-")
    if mode in {"commands", "evidence", "gates", "schema"}:
        return mode
    if validator_id in {"contract", "schema"}:
        return "schema"
    if validator_id in {"screenshot", "evidence"}:
        return "evidence"
    return "commands"


def dev_pipeline_validator_config(
    root: Path,
    project: dict[str, Any],
    template: dict[str, Any],
    validator: dict[str, Any],
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validator_id = dev_pipeline_slug(dev_pipeline_text((payload or {}).get("id"), str(validator.get("id") or "")), "validator")
    receipt_rel = dev_pipeline_text((payload or {}).get("receipt"), str(validator.get("receipt") or f"validation/{validator_id}_receipt.json"))
    config_rel = dev_pipeline_text((payload or {}).get("config_path"), str(validator.get("config") or f"validation/validator_configs/{validator_id}.json"))
    existing_config = dev_pipeline_artifact_json(root, config_rel)
    receipt = dev_pipeline_artifact_json(root, receipt_rel)
    current = existing_config if existing_config else {}
    source = payload if isinstance(payload, dict) else current
    title = dev_pipeline_text(source.get("title"), str(validator.get("title") or validator_id))
    status = dev_pipeline_validation_status(source.get("status"), str(current.get("status") or receipt.get("status") or "configured"))
    mode = dev_pipeline_validator_mode(validator_id, source.get("mode", current.get("mode", "")))
    commands = dev_pipeline_text_list(source.get("commands"), [str(item.get("command") or item.get("name") or "") for item in receipt.get("commands", []) if isinstance(item, dict)])
    if not commands:
        commands = dev_pipeline_default_validation_commands(validator_id)
    evidence = dev_pipeline_text_list(source.get("evidence"), [str(item) for item in receipt.get("evidence", receipt.get("artifacts", [])) if isinstance(item, str)])
    if not evidence and receipt_rel:
        evidence = [receipt_rel]
    gates = dev_pipeline_text_list(source.get("gates"), [str(item) for item in current.get("gates", []) if isinstance(item, str)])
    if not gates:
        gates = ["No failed validation command", "Receipt artifact is attached to evidence bundle", "Blocking validator prevents handoff until resolved"]
    schema_paths = dev_pipeline_text_list(source.get("schema_paths"), [str(item) for item in current.get("schema_paths", []) if isinstance(item, str)])
    if not schema_paths and validator_id in {"contract", "schema"}:
        schema_paths = ["pipeline_manifest.json", "workset.json", "integration_receipts/*.json"]
    summary = dev_pipeline_text(source.get("summary"), str(receipt.get("summary") or f"{title} configured for the integration lane"))
    tier = dev_pipeline_text(source.get("tier"), str(template.get("validation_tier") or receipt.get("tier") or "smoke-plus"))
    source_results = source.get("results") if isinstance(source.get("results"), dict) else None
    receipt_results = receipt.get("results") if isinstance(receipt.get("results"), dict) else {}
    results = deepcopy(source_results if isinstance(source_results, dict) else receipt_results)
    return {
        "schema_version": "cento.validator_config.v1",
        "id": validator_id,
        "project": str(project.get("id") or ""),
        "template_id": str(template.get("id") or ""),
        "title": title,
        "mode": mode,
        "status": status,
        "tier": tier,
        "summary": summary,
        "commands": commands,
        "evidence": evidence,
        "gates": gates,
        "schema_paths": schema_paths,
        "blocking": bool(source.get("blocking", current.get("blocking", True))),
        "receipt": receipt_rel,
        "config_path": config_rel,
        "last_run_mode": str(source.get("last_run_mode") or receipt.get("last_run_mode") or ""),
        "last_run_status": str(source.get("last_run_status") or receipt.get("last_run_status") or ""),
        "executed_at": str(source.get("executed_at") or receipt.get("executed_at") or ""),
        "results": results,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def dev_pipeline_result_status(items: list[dict[str, Any]]) -> str:
    if not items:
        return "configured"
    statuses = {str(item.get("status") or "").lower() for item in items}
    if "failed" in statuses:
        return "failed"
    if "warning" in statuses:
        return "warning"
    if statuses and statuses <= {"passed", "accepted"}:
        return "passed"
    return "configured"


def dev_pipeline_validation_run_status(results: dict[str, Any]) -> str:
    statuses: list[str] = []
    for key in ("commands", "evidence", "gates", "schema"):
        items = results.get(key)
        if isinstance(items, list) and items:
            statuses.append(dev_pipeline_result_status([item for item in items if isinstance(item, dict)]))
    if not statuses:
        return "configured"
    if "failed" in statuses:
        return "failed"
    if "warning" in statuses:
        return "warning"
    if all(status == "passed" for status in statuses):
        return "passed"
    return "configured"


def dev_pipeline_validation_path(root: Path, value: str) -> Path:
    raw = str(value or "").strip()
    path = Path(raw)
    if path.is_absolute():
        return path
    if raw.startswith("workspace/") or raw.startswith("templates/") or raw.startswith("scripts/") or raw.startswith("docs/"):
        return ROOT_DIR / raw
    return root / raw


def dev_pipeline_validation_glob(root: Path, value: str) -> list[Path]:
    raw = str(value or "").strip()
    if not raw:
        return []
    pattern = str(dev_pipeline_validation_path(root, raw))
    matches = [Path(match) for match in glob.glob(pattern)]
    if matches:
        return sorted(matches)
    return [dev_pipeline_validation_path(root, raw)]


def dev_pipeline_relative_validation_path(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT_DIR))
    except ValueError:
        try:
            return str(path.resolve().relative_to(root.resolve()))
        except ValueError:
            return str(path)


def dev_pipeline_run_command(command: str, index: int) -> dict[str, Any]:
    started = time.time()
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT_DIR,
            shell=True,
            text=True,
            capture_output=True,
            timeout=30,
        )
        status = "passed" if completed.returncode == 0 else "failed"
        return {
            "id": f"command-{index}",
            "command": command,
            "status": status,
            "returncode": completed.returncode,
            "duration_ms": int((time.time() - started) * 1000),
            "stdout": completed.stdout[-4000:],
            "stderr": completed.stderr[-4000:],
        }
    except subprocess.TimeoutExpired as error:
        return {
            "id": f"command-{index}",
            "command": command,
            "status": "failed",
            "returncode": 124,
            "duration_ms": int((time.time() - started) * 1000),
            "stdout": str(error.stdout or "")[-4000:],
            "stderr": f"Timed out after 30s\n{str(error.stderr or '')[-3800:]}",
        }


def dev_pipeline_check_evidence(root: Path, evidence: str, index: int) -> dict[str, Any]:
    raw = str(evidence or "").strip()
    if raw.startswith(("http://", "https://")):
        try:
            with urlopen(raw, timeout=5) as response:
                status_code = getattr(response, "status", 200)
            return {"id": f"evidence-{index}", "path": raw, "status": "passed", "kind": "url", "details": f"HTTP {status_code}"}
        except (HTTPError, URLError, TimeoutError) as error:
            return {"id": f"evidence-{index}", "path": raw, "status": "failed", "kind": "url", "details": str(error)}
    path = dev_pipeline_validation_path(root, raw)
    exists = path.exists()
    return {
        "id": f"evidence-{index}",
        "path": raw,
        "resolved_path": dev_pipeline_relative_validation_path(root, path),
        "status": "passed" if exists else "failed",
        "kind": "file",
        "details": "exists" if exists else "missing",
    }


def dev_pipeline_schema_checks(root: Path, schema_paths: list[str]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for index, raw in enumerate(schema_paths, start=1):
        paths = dev_pipeline_validation_glob(root, raw)
        for match_index, path in enumerate(paths, start=1):
            check_id = f"schema-{index}" if len(paths) == 1 else f"schema-{index}-{match_index}"
            if not path.exists():
                checks.append(
                    {
                        "id": check_id,
                        "path": raw,
                        "resolved_path": dev_pipeline_relative_validation_path(root, path),
                        "status": "failed",
                        "details": "missing",
                    }
                )
                continue
            try:
                json.loads(path.read_text(encoding="utf-8"))
                checks.append(
                    {
                        "id": check_id,
                        "path": raw,
                        "resolved_path": dev_pipeline_relative_validation_path(root, path),
                        "status": "passed",
                        "details": "valid JSON",
                    }
                )
            except (OSError, json.JSONDecodeError) as error:
                checks.append(
                    {
                        "id": check_id,
                        "path": raw,
                        "resolved_path": dev_pipeline_relative_validation_path(root, path),
                        "status": "failed",
                        "details": str(error),
                    }
                )
    return checks


def dev_pipeline_gate_checks(root: Path, config: dict[str, Any], results: dict[str, Any]) -> list[dict[str, Any]]:
    integration_lane = dev_pipeline_artifact_json(root, "integration/integration_lane.json")
    lane_steps = [step for step in integration_lane.get("steps", []) if isinstance(step, dict)]
    blocked_or_rejected = [
        str(step.get("id") or step.get("title") or "")
        for step in lane_steps
        if str(step.get("status") or "").lower() in {"blocked", "rejected"}
    ]
    command_results = [item for item in results.get("commands", []) if isinstance(item, dict)]
    checks: list[dict[str, Any]] = []
    for index, gate in enumerate([str(item) for item in config.get("gates", []) if isinstance(item, str)], start=1):
        normalized = gate.lower()
        status = "passed"
        details = "declared gate is non-empty"
        if "no failed validation command" in normalized:
            failed = [item.get("id") or item.get("command") for item in command_results if str(item.get("status") or "") == "failed"]
            status = "failed" if failed else "passed"
            details = "no failed commands" if not failed else f"failed commands: {', '.join(map(str, failed))}"
        elif "receipt artifact" in normalized and "attached" in normalized:
            receipt = str(config.get("receipt") or "")
            evidence = [str(item) for item in config.get("evidence", []) if isinstance(item, str)]
            status = "passed" if receipt and (receipt in evidence or dev_pipeline_validation_path(root, receipt).exists()) else "failed"
            details = f"receipt {receipt} {'attached or exists' if status == 'passed' else 'not attached'}"
        elif "blocking validator" in normalized:
            status = "passed" if bool(config.get("blocking", True)) else "failed"
            details = "blocking enabled" if status == "passed" else "blocking disabled"
        elif "no blocked or rejected" in normalized or "owned-path overlap" in normalized:
            status = "failed" if blocked_or_rejected else "passed"
            details = "integration lane clear" if not blocked_or_rejected else f"blocked/rejected: {', '.join(blocked_or_rejected)}"
        elif normalized.startswith("dependency receipt accepted:"):
            dependency = gate.split(":", 1)[-1].strip()
            matching = next((step for step in lane_steps if str(step.get("id") or "") == dependency), None)
            if matching is None:
                status = "warning"
                details = f"dependency {dependency} not present in integration lane"
            else:
                step_status = str(matching.get("status") or "").lower()
                status = "passed" if step_status in {"accepted", "merged", "configured"} else "failed"
                details = f"dependency {dependency} status {step_status or 'unknown'}"
        checks.append({"id": f"gate-{index}", "gate": gate, "status": status, "details": details})
    return checks


def dev_pipeline_execute_validation(root: Path, config: dict[str, Any], run_mode: str) -> dict[str, Any]:
    mode = "all" if str(run_mode or "").lower() == "all" else dev_pipeline_validator_mode(str(config.get("id") or ""), run_mode)
    modes = ["commands", "evidence", "gates", "schema"] if mode == "all" else [mode]
    existing_results = config.get("results") if isinstance(config.get("results"), dict) else {}
    results = deepcopy(existing_results)
    if "commands" in modes:
        results["commands"] = [
            dev_pipeline_run_command(command, index)
            for index, command in enumerate([str(item) for item in config.get("commands", []) if isinstance(item, str) and item.strip()], start=1)
        ]
    if "evidence" in modes:
        results["evidence"] = [
            dev_pipeline_check_evidence(root, evidence, index)
            for index, evidence in enumerate([str(item) for item in config.get("evidence", []) if isinstance(item, str) and item.strip()], start=1)
        ]
    if "schema" in modes:
        results["schema"] = dev_pipeline_schema_checks(root, [str(item) for item in config.get("schema_paths", []) if isinstance(item, str) and item.strip()])
    if "gates" in modes:
        results["gates"] = dev_pipeline_gate_checks(root, config, results)
    status = dev_pipeline_validation_run_status(results)
    executed = deepcopy(config)
    executed["results"] = results
    executed["status"] = status
    executed["last_run_status"] = status
    executed["last_run_mode"] = mode
    executed["executed_at"] = datetime.now(timezone.utc).isoformat()
    return executed


def dev_pipeline_write_validation_outputs(root: Path, manifest: dict[str, Any], project: dict[str, Any], template: dict[str, Any], config: dict[str, Any]) -> None:
    validator_id = str(config.get("id") or "validator")
    validators = [item for item in template.get("validators", []) if isinstance(item, dict)]
    validator = next((item for item in validators if str(item.get("id") or "") == validator_id), None)
    if validator is None:
        validator = {"id": validator_id}
        validators.append(validator)
        template["validators"] = validators
    validator["id"] = validator_id
    validator["title"] = str(config.get("title") or validator_id)
    validator["file"] = Path(str(config.get("receipt") or f"validation/{validator_id}_receipt.json")).name
    validator["receipt"] = str(config.get("receipt") or f"validation/{validator_id}_receipt.json")
    validator["config"] = str(config.get("config_path") or f"validation/validator_configs/{validator_id}.json")
    validator["mode"] = str(config.get("mode") or "commands")
    validator["blocking"] = bool(config.get("blocking", True))
    validator["status"] = str(config.get("status") or "configured")

    config_path = dev_pipeline_root_path(root, str(validator["config"]))
    write_json_path(config_path, config)

    results = config.get("results") if isinstance(config.get("results"), dict) else {}
    command_results = [item for item in results.get("commands", []) if isinstance(item, dict)]
    command_status_by_text = {
        str(item.get("command") or ""): str(item.get("status") or config.get("status") or "configured")
        for item in command_results
    }
    receipt_commands = [
        {
            "name": dev_pipeline_slug(command.split()[0] if command else f"command-{index}", f"command-{index}"),
            "command": command,
            "status": command_status_by_text.get(str(command), str(config.get("status") or "configured")),
        }
        for index, command in enumerate(config.get("commands") or [], start=1)
    ]
    receipt_payload = {
        "schema_version": "cento.validator_receipt.v1",
        "id": validator_id,
        "status": str(config.get("status") or "configured"),
        "tier": str(config.get("tier") or template.get("validation_tier") or ""),
        "summary": str(config.get("summary") or ""),
        "mode": str(config.get("mode") or "commands"),
        "blocking": bool(config.get("blocking", True)),
        "commands": receipt_commands,
        "evidence": [str(item) for item in config.get("evidence", []) if isinstance(item, str)],
        "gates": [str(item) for item in config.get("gates", []) if isinstance(item, str)],
        "schema_paths": [str(item) for item in config.get("schema_paths", []) if isinstance(item, str)],
        "results": results,
        "last_run_mode": str(config.get("last_run_mode") or ""),
        "last_run_status": str(config.get("last_run_status") or ""),
        "executed_at": str(config.get("executed_at") or ""),
        "config": str(validator["config"]),
        "written_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json_path(dev_pipeline_root_path(root, str(validator["receipt"])), receipt_payload)

    validator_checks: list[dict[str, Any]] = []
    aggregate_commands: list[dict[str, Any]] = []
    aggregate_artifacts: list[str] = []
    aggregate_statuses: list[str] = []
    for item in validators:
        item_id = str(item.get("id") or "")
        item_config = dev_pipeline_validator_config(root, project, template, item)
        aggregate_statuses.append(str(item_config.get("status") or "configured"))
        aggregate_artifacts.extend([str(item_config.get("receipt") or ""), str(item_config.get("config_path") or "")])
        validator_checks.append(
            {
                "id": item_id,
                "title": str(item_config.get("title") or item_id),
                "type": str(item_config.get("mode") or "commands"),
                "status": str(item_config.get("status") or "configured"),
                "blocking": bool(item_config.get("blocking", True)),
                "commands": [str(value) for value in item_config.get("commands", []) if isinstance(value, str)],
                "evidence": [str(value) for value in item_config.get("evidence", []) if isinstance(value, str)],
                "gates": [str(value) for value in item_config.get("gates", []) if isinstance(value, str)],
                "schema_paths": [str(value) for value in item_config.get("schema_paths", []) if isinstance(value, str)],
                "last_run_mode": str(item_config.get("last_run_mode") or ""),
                "last_run_status": str(item_config.get("last_run_status") or ""),
                "executed_at": str(item_config.get("executed_at") or ""),
                "results": item_config.get("results") if isinstance(item_config.get("results"), dict) else {},
                "config": str(item_config.get("config_path") or ""),
                "receipt": str(item_config.get("receipt") or ""),
            }
        )
        for command in item_config.get("commands", []):
            if isinstance(command, str) and command.strip():
                aggregate_commands.append(
                    {
                        "name": f"{item_id}_{dev_pipeline_slug(command.split()[0], 'command')}",
                        "command": command,
                        "status": str(item_config.get("status") or "configured"),
                    }
                )

    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), dict) else {}
    validator_manifest_rel = str(artifacts.get("validator_manifest") or "validation/validator_manifest.json")
    validator_manifest = {
        "schema_version": "cento.validator_manifest.v1",
        "id": f"{template.get('id') or 'pipeline'}-validator",
        "pipeline_manifest": "pipeline_manifest.json",
        "project": str(project.get("id") or ""),
        "template_id": str(template.get("id") or ""),
        "validation_tier": str(config.get("tier") or template.get("validation_tier") or ""),
        "validation_policy": {
            "mode": "post-integration",
            "blocking_validators": [str(item.get("id") or "") for item in validators if bool(item.get("blocking", True))],
            "receipt_policy": "write validator config, validator receipt, aggregate validation receipt, and evidence references after integration receipts exist",
        },
        "checks": validator_checks,
        "written_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json_path(dev_pipeline_root_path(root, validator_manifest_rel), validator_manifest)

    aggregate_status = "configured"
    if any(status == "failed" for status in aggregate_statuses):
        aggregate_status = "failed"
    elif aggregate_statuses and all(status == "passed" for status in aggregate_statuses):
        aggregate_status = "passed"
    validation_receipt_rel = str(artifacts.get("validation_receipt") or "validation/validation_receipt.json")
    validation_receipt = {
        "schema_version": "cento.validation_receipt.v1",
        "manifest_id": str(manifest.get("id") or ""),
        "project": str(project.get("id") or ""),
        "template_id": str(template.get("id") or ""),
        "tier": str(config.get("tier") or template.get("validation_tier") or ""),
        "status": aggregate_status,
        "commands": aggregate_commands,
        "artifacts": [item for item in dict.fromkeys(aggregate_artifacts) if item],
        "validator_manifest": validator_manifest_rel,
        "validation_policy": validator_manifest["validation_policy"],
        "results": {
            str(check.get("id") or ""): check.get("results") if isinstance(check.get("results"), dict) else {}
            for check in validator_checks
            if str(check.get("id") or "")
        },
        "written_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json_path(dev_pipeline_root_path(root, validation_receipt_rel), validation_receipt)


def dev_pipeline_evidence_status(value: Any, current: str = "configured") -> str:
    raw = dev_pipeline_text(value, current).lower().replace("_", "-").replace(" ", "-")
    if raw.endswith(" events"):
        return "logged"
    if raw.startswith("$"):
        return "within-budget"
    aliases = {
        "complete": "completed",
        "done": "completed",
        "attached": "attached",
        "review-ready": "review",
        "review ready": "review",
        "within budget": "within-budget",
        "within-budget": "within-budget",
    }
    status = aliases.get(raw, raw)
    allowed = {"completed", "attached", "review", "configured", "logged", "within-budget", "missing", "failed"}
    if status in allowed:
        return status
    return current if current in allowed else "configured"


def dev_pipeline_evidence_kind(value: Any, evidence_id: str = "") -> str:
    raw = dev_pipeline_text(value, "").lower().replace("_", "-").replace(" ", "-")
    aliases = {
        "events": "event-log",
        "log": "event-log",
        "receipt": "receipt",
        "pipeline-receipt": "receipt",
        "evidence-bundle": "bundle",
        "bundle": "bundle",
        "budget-receipt": "budget",
        "taskstream-evidence": "taskstream",
    }
    kind = aliases.get(raw, raw)
    if kind in {"receipt", "event-log", "bundle", "budget", "taskstream", "artifact"}:
        return kind
    evidence_id = str(evidence_id or "").replace("_", "-")
    if evidence_id == "events":
        return "event-log"
    if evidence_id in {"evidence-bundle", "evidence_bundle"}:
        return "bundle"
    if evidence_id == "budget":
        return "budget"
    if evidence_id == "taskstream":
        return "taskstream"
    if evidence_id in {"pipeline-receipt", "pipeline_receipt"}:
        return "receipt"
    return "artifact"


def dev_pipeline_default_evidence_sources(evidence_id: str) -> list[str]:
    defaults = {
        "pipeline_receipt": ["pipeline_manifest.json", "workset.json", "validation/validation_receipt.json"],
        "pipeline-receipt": ["pipeline_manifest.json", "workset.json", "validation/validation_receipt.json"],
        "events": ["events.ndjson"],
        "evidence_bundle": ["pipeline_manifest.json", "integration_receipts/*.json", "validation/validation_receipt.json", "evidence/budget_receipt.json"],
        "evidence-bundle": ["pipeline_manifest.json", "integration_receipts/*.json", "validation/validation_receipt.json", "evidence/budget_receipt.json"],
        "budget": ["evidence/budget_receipt.json", "pipeline_manifest.json"],
        "taskstream": ["evidence/taskstream_evidence.json", "workspace/runs/agent-work/*/validation-report.json"],
    }
    return defaults.get(str(evidence_id or ""), ["pipeline_manifest.json"])


def dev_pipeline_evidence_config(
    root: Path,
    manifest: dict[str, Any],
    project: dict[str, Any],
    template: dict[str, Any],
    artifact: dict[str, Any],
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    evidence_id = dev_pipeline_slug(dev_pipeline_text((payload or {}).get("id"), str(artifact.get("id") or "")), "evidence")
    path_rel = dev_pipeline_text((payload or {}).get("path"), str(artifact.get("path") or f"evidence/{evidence_id}.json"))
    config_rel = dev_pipeline_text((payload or {}).get("config_path"), str(artifact.get("config") or f"evidence/configs/{evidence_id}.json"))
    existing_config = dev_pipeline_artifact_json(root, config_rel)
    artifact_json = dev_pipeline_artifact_json(root, path_rel) if path_rel.endswith(".json") else {}
    current = existing_config if existing_config else {}
    source = payload if isinstance(payload, dict) else current
    title = dev_pipeline_text(source.get("title"), str(artifact.get("title") or evidence_id.replace("-", " ").title()))
    status = dev_pipeline_evidence_status(source.get("status"), dev_pipeline_evidence_status(current.get("status"), dev_pipeline_evidence_status(artifact_json.get("status"), dev_pipeline_evidence_status(artifact.get("state") or artifact.get("status"), "configured"))))
    kind = dev_pipeline_evidence_kind(source.get("kind", current.get("kind", artifact.get("kind", ""))), evidence_id)
    required_sources = dev_pipeline_text_list(source.get("required_sources"), [str(item) for item in current.get("required_sources", []) if isinstance(item, str)])
    if not required_sources:
        required_sources = dev_pipeline_default_evidence_sources(str(artifact.get("id") or evidence_id))
    publish_policy = dev_pipeline_text(source.get("publish_policy"), str(current.get("publish_policy") or "Attach to evidence bundle before Taskstream review"))
    retention_policy = dev_pipeline_text(source.get("retention_policy"), str(current.get("retention_policy") or "Keep with the pipeline run artifacts"))
    review_notes = dev_pipeline_text(source.get("review_notes"), str(current.get("review_notes") or ""))
    return {
        "schema_version": "cento.evidence_config.v1",
        "id": evidence_id,
        "project": str(project.get("id") or ""),
        "template_id": str(template.get("id") or ""),
        "title": title,
        "kind": kind,
        "status": status,
        "path": path_rel,
        "config_path": config_rel,
        "required_sources": required_sources,
        "publish_policy": publish_policy,
        "retention_policy": retention_policy,
        "review_notes": review_notes,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def dev_pipeline_write_evidence_outputs(root: Path, manifest: dict[str, Any], project: dict[str, Any], template: dict[str, Any], config: dict[str, Any]) -> None:
    config_path = dev_pipeline_root_path(root, str(config.get("config_path") or f"evidence/configs/{config.get('id') or 'evidence'}.json"))
    artifact_rel = str(config.get("path") or "")
    artifact_path = dev_pipeline_root_path(root, artifact_rel)
    write_json_path(config_path, config)

    if artifact_rel.endswith(".ndjson"):
        dev_pipeline_append_event(
            root,
            manifest,
            "pipeline_evidence_configured",
            str(project.get("id") or ""),
            str(template.get("id") or ""),
            {
                "evidence_id": str(config.get("id") or ""),
                "title": str(config.get("title") or ""),
                "status": str(config.get("status") or ""),
                "config": str(config.get("config_path") or ""),
            },
        )
    else:
        existing = read_json_path(artifact_path)
        payload = deepcopy(existing) if existing else {}
        payload.setdefault("schema_version", f"cento.{str(config.get('kind') or 'evidence').replace('-', '_')}.v1")
        payload["title"] = str(config.get("title") or "")
        payload["status"] = str(config.get("status") or "configured")
        payload["evidence_config"] = str(config.get("config_path") or "")
        payload["required_sources"] = [str(item) for item in config.get("required_sources", []) if isinstance(item, str)]
        payload["publish_policy"] = str(config.get("publish_policy") or "")
        payload["retention_policy"] = str(config.get("retention_policy") or "")
        payload["review_notes"] = str(config.get("review_notes") or "")
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        write_json_path(artifact_path, payload)

    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), dict) else {}
    artifacts["evidence_manifest"] = str(artifacts.get("evidence_manifest") or "evidence/evidence_manifest.json")
    manifest["artifacts"] = artifacts
    manifest_config_rel = str(artifacts["evidence_manifest"])
    known_configs = sorted({str(config.get("config_path") or "")} | set(str(item) for item in dev_pipeline_artifact_json(root, manifest_config_rel).get("configs", []) if isinstance(item, str)))
    evidence_manifest = {
        "schema_version": "cento.evidence_manifest.v1",
        "project": str(project.get("id") or ""),
        "template_id": str(template.get("id") or ""),
        "status": "configured",
        "configs": [item for item in known_configs if item],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json_path(dev_pipeline_root_path(root, manifest_config_rel), evidence_manifest)


def dev_pipeline_generic_blueprint_defaults() -> dict[str, Any]:
    return {
        "label": "Generic easy task",
        "detail": "Fully configured non-UI easy programming blueprint",
        "description": "Bounded programming task contracts with deterministic discovery, Factory execution, validation, and evidence handoff for one small repo-local change.",
        "tagline": "Small scoped repo change with validation evidence",
        "worker_type": "automation_contract_worker",
        "execution_model": "ordered",
        "worker_stage_label": "2. Repo Discovery",
        "factory_stage_label": "4. Factory Execution",
        "selected_worker": "repo-context",
        "blueprint_version": "automation-contracts.v1",
        "tasks_completed": 9,
        "tasks_total": 9,
        "workers": [
            {
                "id": "repo-context",
                "title": "Repo Context Manifest",
                "file": "repo_context.json",
                "description": "Discover languages, test commands, ownership hints, and dependency graph source",
                "stage": "repo",
                "manifest": "workers/generic-task_repo-context.json",
                "integration_config": "integration/configs/repo-context.json",
                "integration_receipt": "integration_receipts/generic-task_repo-context.json",
            },
            {
                "id": "change-blueprint",
                "title": "Change Plan Contract",
                "file": "change_plan.json",
                "description": "Define bounded change units, test units, and optional AI review gates",
                "stage": "blueprint",
                "dependencies": ["repo-context"],
                "manifest": "workers/generic-task_change-blueprint.json",
                "integration_config": "integration/configs/change-blueprint.json",
                "integration_receipt": "integration_receipts/generic-task_change-blueprint.json",
            },
        ],
        "factory_steps": [
            {"id": "checkout-branch", "title": "checkout_branch", "file": "execution_manifest.json", "status": "accepted", "mode": "deterministic"},
            {"id": "snapshot-repo-state", "title": "snapshot_repo_state", "file": "repo_snapshot.json", "status": "accepted", "mode": "deterministic", "dependencies": ["checkout-branch"]},
            {"id": "apply-change-units", "title": "apply_change_units", "file": "factory_apply_receipt.json", "status": "accepted", "mode": "deterministic", "dependencies": ["snapshot-repo-state"]},
            {"id": "run-formatters", "title": "run_formatters", "file": "format_receipt.json", "status": "accepted", "mode": "deterministic", "dependencies": ["apply-change-units"]},
            {"id": "run-focused-tests", "title": "run_focused_tests", "file": "focused_tests.log", "status": "accepted", "mode": "deterministic", "dependencies": ["run-formatters"]},
            {"id": "run-full-tests", "title": "run_full_tests", "file": "full_tests.log", "status": "accepted", "mode": "deterministic", "dependencies": ["run-focused-tests"]},
            {"id": "collect-diff", "title": "collect_diff", "file": "diff.patch", "status": "accepted", "mode": "deterministic", "dependencies": ["run-full-tests"]},
            {"id": "collect-logs", "title": "collect_logs", "file": "evidence_manifest.json", "status": "accepted", "mode": "deterministic", "dependencies": ["collect-diff"]},
        ],
    }


def dev_pipeline_apply_generic_blueprint(template: dict[str, Any]) -> dict[str, Any]:
    if str(template.get("id") or "") != "generic-task":
        return template
    defaults = dev_pipeline_generic_blueprint_defaults()
    def merge_default_fields(current: dict[str, Any], default: dict[str, Any]) -> dict[str, Any]:
        merged = deepcopy(current)
        for key, value in default.items():
            if key not in merged or merged.get(key) is None:
                merged[key] = deepcopy(value)
        return merged

    for key in ("label", "detail", "description", "tagline", "worker_type", "execution_model", "worker_stage_label", "factory_stage_label", "blueprint_version", "tasks_completed", "tasks_total"):
        if key not in template or template.get(key) is None or (isinstance(template.get(key), str) and not str(template.get(key)).strip()):
            template[key] = deepcopy(defaults[key])

    default_workers = {
        str(item.get("id") or ""): item
        for item in defaults["workers"]
        if isinstance(item, dict)
    }
    raw_workers = template.get("workers")
    if isinstance(raw_workers, list):
        template["workers"] = [
            merge_default_fields(item, default_workers.get(str(item.get("id") or ""), {}))
            for item in raw_workers
            if isinstance(item, dict)
        ]
    else:
        template["workers"] = deepcopy(defaults["workers"])

    default_steps = {
        str(item.get("id") or ""): item
        for item in defaults["factory_steps"]
        if isinstance(item, dict)
    }
    raw_steps = template.get("factory_steps")
    if isinstance(raw_steps, list):
        template["factory_steps"] = [
            merge_default_fields(item, default_steps.get(str(item.get("id") or ""), {}))
            for item in raw_steps
            if isinstance(item, dict)
        ]
    else:
        template["factory_steps"] = deepcopy(defaults["factory_steps"])

    default_inputs = dev_pipeline_default_required_inputs("generic-task")
    default_input_map = {
        str(item.get("id") or ""): item
        for item in default_inputs
        if isinstance(item, dict)
    }
    raw_inputs = template.get("required_inputs")
    if isinstance(raw_inputs, list):
        template["required_inputs"] = [
            merge_default_fields(item, default_input_map.get(str(item.get("id") or ""), {}))
            for item in raw_inputs
            if isinstance(item, dict)
        ]
    else:
        template["required_inputs"] = default_inputs

    workers = [worker for worker in template.get("workers", []) if isinstance(worker, dict)]
    if not any(str(worker.get("id") or "") == str(template.get("selected_worker") or "") for worker in workers):
        template["selected_worker"] = str(workers[0].get("id") or "") if workers else ""
    return template


def dev_pipeline_default_required_inputs(template_id: str) -> list[dict[str, Any]]:
    template_id = str(template_id or "")
    defaults: dict[str, list[dict[str, Any]]] = {
        "generic-task": [
            {
                "id": "input-manifest",
                "title": "Input manifest",
                "detail": "Task kind, surface, target paths, allowed changes, forbidden changes, and acceptance boundaries",
                "kind": "details",
                "format": "JSON object",
                "artifacts": ["workspace/runs/generic-task/outputs/scope.json", "workspace/runs/generic-task/outputs/plan.json"],
                "evidence_policy": "The input manifest must identify the task kind, expected behavior, target surface, allowed changes, forbidden changes, and acceptance boundary before workers start.",
                "status": "provided",
                "required": True,
            },
            {
                "id": "repo-context-manifest",
                "title": "Repo context manifest",
                "detail": "Languages, test commands, lint commands, ownership hints, and dependency graph source",
                "kind": "path",
                "paths": ["AGENTS.md", "README.md", "scripts/**", "templates/agent-work-app/**", "docs/**", "tests/**"],
                "path_policy": "Discover repo contracts before any code synthesis or Factory execution",
                "artifacts": ["workspace/runs/dev-pipeline-studio/docs-pages/latest/workers/generic-task_repo-context.json"],
                "evidence_policy": "Repo context must name existing conventions, runnable validation commands, and ownership hints before change planning starts.",
                "status": "configured",
                "required": True,
            },
            {
                "id": "change-blueprint-contract",
                "title": "Change blueprint contract",
                "detail": "Structured change units, test units, expected symbols, and ambiguity gates",
                "kind": "questionnaire",
                "questions": [
                    {"id": "q-1", "prompt": "Which bounded behavior should change?", "required": True, "answer_type": "text", "options": []},
                    {"id": "q-2", "prompt": "Which files or symbols are expected targets?", "required": False, "answer_type": "text", "options": []},
                    {"id": "q-3", "prompt": "Which cases must focused tests cover?", "required": True, "answer_type": "multi-select", "options": ["success", "failure", "edge_case", "regression"]},
                ],
                "artifacts": ["workspace/runs/dev-pipeline-studio/docs-pages/latest/workers/generic-task_change-blueprint.json"],
                "evidence_policy": "Blueprint must map each change unit to an owned path, validation command, rollback note, and handoff artifact.",
                "status": "configured",
                "required": True,
            },
            {
                "id": "execution-manifest",
                "title": "Execution manifest",
                "detail": "Checkout, snapshot, apply change units, formatters, tests, diff collection, logs, and rollback limits",
                "kind": "details",
                "format": "JSON object",
                "artifacts": [
                    "workspace/runs/dev-pipeline-studio/docs-pages/latest/integration/configs/repo-context.json",
                    "workspace/runs/dev-pipeline-studio/docs-pages/latest/integration/configs/change-blueprint.json",
                    "workspace/runs/dev-pipeline-studio/docs-pages/latest/integration/integration_lane.json"
                ],
                "evidence_policy": "Factory execution must have checkout, snapshot, apply, formatting, test, diff, log, and rollback steps configured before handoff.",
                "status": "configured",
                "required": True,
            },
            {
                "id": "validation-evidence-manifest",
                "title": "Validation and evidence manifest",
                "detail": "Deterministic checks first; optional AI review only on large diffs, failures, or ambiguous acceptance",
                "kind": "evidence",
                "artifacts": [
                    "diff.patch",
                    "test-output.txt",
                    "validation-report.json",
                    "acceptance-map.md",
                    "risk-notes.md",
                    "workspace/runs/dev-pipeline-studio/docs-pages/latest/validation/validation_receipt.json",
                    "workspace/runs/dev-pipeline-studio/docs-pages/latest/evidence/evidence_bundle.json"
                ],
                "evidence_policy": "Factory executes the blueprint; validators decide acceptability before human handoff, and the evidence bundle must include manifest, integration, validation, budget, Taskstream, and handoff artifacts.",
                "status": "configured",
                "required": True,
            },
        ],
        "doc-page": [
            {
                "id": "page-brief",
                "title": "Page brief",
                "detail": "Audience, page objective, product surface, and desired outcome",
                "kind": "details",
                "format": "markdown",
                "status": "provided",
                "required": True,
            },
            {
                "id": "reference-images",
                "title": "Reference images",
                "detail": "Screenshots, mockups, or visual references for the doc page",
                "kind": "image",
                "image_refs": ["Downloads/devpipelinestudio.png"],
                "image_notes": "Inspect layout, hierarchy, visual density, and sidebar/content alignment",
                "status": "configured",
                "required": False,
            },
            {
                "id": "content-questionnaire",
                "title": "Content questionnaire",
                "detail": "Structured questions required before workers generate sections",
                "kind": "questionnaire",
                "questions": [
                    {"id": "q-1", "prompt": "What is the primary reader task?", "required": True, "answer_type": "text", "options": []},
                    {"id": "q-2", "prompt": "Which sections are mandatory?", "required": True, "answer_type": "multi-select", "options": ["Overview", "User guide", "Data model", "Changelog"]},
                    {"id": "q-3", "prompt": "Which links or external references must be included?", "required": False, "answer_type": "text", "options": []},
                ],
                "status": "configured",
                "required": True,
            },
            {
                "id": "target-doc-paths",
                "title": "Target doc paths",
                "detail": "Routes and files the doc page pipeline may read or write",
                "kind": "path",
                "paths": ["templates/agent-work-app/index.html", "templates/agent-work-app/styles.css", "/docs#pipeline-studio-template-editor"],
                "path_policy": "Workers may only change declared doc page sections and route-owned assets",
                "status": "configured",
                "required": True,
            },
            {
                "id": "evidence-requirements",
                "title": "Evidence requirements",
                "detail": "Screenshots, receipts, and validation outputs required for handoff",
                "kind": "evidence",
                "artifacts": ["workspace/runs/agent-work/<issue>/typed-inputs.png", "validation/validation_receipt.json"],
                "evidence_policy": "Screenshot must show the typed input editor and manifest path after save",
                "status": "missing",
                "required": True,
            },
        ],
    }
    return dev_pipeline_required_inputs(defaults.get(template_id, []))


def dev_pipeline_template_required_inputs(template: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(template.get("required_inputs"), list):
        return dev_pipeline_required_inputs(template.get("required_inputs"))
    return dev_pipeline_default_required_inputs(str(template.get("id") or ""))


def dev_pipeline_write_input_manifests(root: Path, manifest: dict[str, Any], project: dict[str, Any], template: dict[str, Any], inputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    template_id = str(template.get("id") or "pipeline")
    input_manifest_rel = str(template.get("input_manifest") or f"inputs/{template_id}_input_manifest.json")
    pipeline_config_rel = str(template.get("pipeline_config") or f"inputs/{template_id}_pipeline_config.json")
    normalized_inputs: list[dict[str, Any]] = []
    for item in dev_pipeline_required_inputs(inputs):
        input_id = str(item.get("id") or "input")
        item_manifest_rel = str(item.get("manifest") or f"inputs/{template_id}_{input_id}.json")
        answer = str(item.get("answer") or "")
        answer_values = [str(value) for value in item.get("answer_values", []) if isinstance(value, str)]
        answer_notes = str(item.get("answer_notes") or "")
        answer_present = bool(answer.strip() or answer_values or answer_notes.strip())
        provided_at = str(item.get("provided_at") or "")
        if answer_present and not provided_at:
            provided_at = datetime.now(timezone.utc).isoformat()
        typed_payload = {
            "schema_version": "cento.input_manifest.v1",
            "id": input_id,
            "project": str(project.get("id") or ""),
            "template_id": template_id,
            "title": str(item.get("title") or ""),
            "kind": str(item.get("kind") or item.get("input_type") or "text"),
            "format": str(item.get("format") or ""),
            "status": str(item.get("status") or "missing"),
            "required": bool(item.get("required", True)),
            "detail": str(item.get("detail") or ""),
            "image_refs": [str(value) for value in item.get("image_refs", []) if isinstance(value, str)],
            "image_notes": str(item.get("image_notes") or ""),
            "questions": [question for question in item.get("questions", []) if isinstance(question, dict)],
            "paths": [str(value) for value in item.get("paths", []) if isinstance(value, str)],
            "path_policy": str(item.get("path_policy") or ""),
            "artifacts": [str(value) for value in item.get("artifacts", []) if isinstance(value, str)],
            "evidence_policy": str(item.get("evidence_policy") or ""),
            "answer": answer,
            "answer_values": answer_values,
            "answer_notes": answer_notes,
            "answer_present": answer_present,
            "provided_at": provided_at,
            "written_at": datetime.now(timezone.utc).isoformat(),
        }
        write_json_path(dev_pipeline_root_path(root, item_manifest_rel), typed_payload)
        saved_item = deepcopy(item)
        saved_item["answer"] = answer
        saved_item["answer_values"] = answer_values
        saved_item["answer_notes"] = answer_notes
        saved_item["answer_present"] = answer_present
        saved_item["provided_at"] = provided_at
        saved_item["manifest"] = item_manifest_rel
        normalized_inputs.append(saved_item)

    missing_required = [
        item for item in normalized_inputs
        if bool(item.get("required", True)) and str(item.get("status") or "") == "missing"
    ]
    aggregate_manifest = {
        "schema_version": "cento.input_manifest_set.v1",
        "manifest_id": str(manifest.get("id") or ""),
        "project": str(project.get("id") or ""),
        "template_id": template_id,
        "inputs": [
            {
                "id": str(item.get("id") or ""),
                "title": str(item.get("title") or ""),
                "kind": str(item.get("kind") or ""),
                "status": str(item.get("status") or ""),
                "required": bool(item.get("required", True)),
                "answer_present": bool(item.get("answer_present", False)),
                "answer": str(item.get("answer") or ""),
                "answer_values": [str(value) for value in item.get("answer_values", []) if isinstance(value, str)],
                "answer_notes": str(item.get("answer_notes") or ""),
                "provided_at": str(item.get("provided_at") or ""),
                "manifest": str(item.get("manifest") or ""),
            }
            for item in normalized_inputs
        ],
        "provided_count": len([item for item in normalized_inputs if bool(item.get("answer_present", False))]),
        "missing_required_inputs": [str(item.get("id") or "") for item in missing_required],
        "written_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json_path(dev_pipeline_root_path(root, input_manifest_rel), aggregate_manifest)
    pipeline_config = {
        "schema_version": "cento.pipeline_config.v1",
        "manifest_id": str(manifest.get("id") or ""),
        "project": str(project.get("id") or ""),
        "template_id": template_id,
        "input_manifest": input_manifest_rel,
        "inputs": [
            {
                "id": str(item.get("id") or ""),
                "title": str(item.get("title") or ""),
                "kind": str(item.get("kind") or ""),
                "status": str(item.get("status") or ""),
                "answer": str(item.get("answer") or ""),
                "answer_values": [str(value) for value in item.get("answer_values", []) if isinstance(value, str)],
                "answer_notes": str(item.get("answer_notes") or ""),
                "answer_present": bool(item.get("answer_present", False)),
                "provided_at": str(item.get("provided_at") or ""),
            }
            for item in normalized_inputs
        ],
        "ready_for_run": not missing_required,
        "written_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json_path(dev_pipeline_root_path(root, pipeline_config_rel), pipeline_config)
    template["input_manifest"] = input_manifest_rel
    template["pipeline_config"] = pipeline_config_rel
    return normalized_inputs


def dev_pipeline_append_event(root: Path, manifest: dict[str, Any], event: str, project_id: str, template_id: str, details: dict[str, Any] | None = None) -> None:
    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), dict) else {}
    events_rel = str(artifacts.get("events") or "events.ndjson")
    event_path = dev_pipeline_root_path(root, events_rel)
    event_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "project_id": project_id,
        "template_id": template_id,
        "details": details or {},
    }
    with event_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def dev_pipeline_artifact(root: Path, relative: str) -> dict[str, Any]:
    clean = str(relative or "").strip()
    path = root / clean if clean else root
    return artifact_payload(Path(clean).name or "artifact", dev_pipeline_relative(path), source="dev-pipeline-studio")


def dev_pipeline_artifact_json(root: Path, relative: str) -> dict[str, Any]:
    clean = str(relative or "").strip()
    if not clean:
        return {}
    return read_json_path(root / clean)


def dev_pipeline_find(items: list[dict[str, Any]], requested: str, default_id: str) -> dict[str, Any]:
    wanted = str(requested or default_id or "").strip()
    for item in items:
        aliases = [str(value) for value in item.get("aliases", []) if isinstance(value, str)]
        if str(item.get("id") or "") == wanted or wanted in aliases:
            return item
    for item in items:
        if str(item.get("id") or "") == default_id:
            return item
    return items[0] if items else {}


def dev_pipeline_worker_manifest(project: dict[str, Any], template: dict[str, Any], worker: dict[str, Any], root: Path) -> tuple[dict[str, Any], str]:
    manifest_rel = str(worker.get("manifest") or "").strip()
    payload = dev_pipeline_artifact_json(root, manifest_rel)
    project_id = str(project.get("id") or "")
    template_id = str(template.get("id") or "")
    worker_id = str(worker.get("id") or "")
    if payload and payload.get("project") == project_id and payload.get("template_id") == template_id:
        return payload, manifest_rel

    file_name = str(worker.get("file") or f"{worker_id}.json")
    read_paths = [str(value) for value in project.get("read_paths", []) if isinstance(value, str)]
    read_paths.append(f"templates/pipelines/{template_id}.json")
    payload = {
        "schema_version": "cento.worker_manifest.v1",
        "id": f"{worker_id}_worker_01",
        "project": project_id,
        "template_id": template_id,
        "type": str(template.get("worker_type") or "pipeline_worker"),
        "task_id": worker_id,
        "description": f"{worker.get('description') or worker.get('title') or worker_id} for {project.get('label') or project_id} using the {template.get('label') or template_id} template",
        "owned_paths": [f"{project.get('owned_root') or 'workspace/generated'}/{file_name}"],
        "read_paths": read_paths,
        "dependencies": [],
        "acceptance": [
            f"{template.get('label') or 'Template'} output is valid",
            "Template parameters are preserved",
            "Only owned paths changed",
        ],
        "validation": {"tier": str(template.get("validation_tier") or "smoke")},
    }
    return payload, manifest_rel


def dev_pipeline_synthesized_worker_manifest(project: dict[str, Any], template: dict[str, Any], worker: dict[str, Any]) -> dict[str, Any]:
    worker_id = str(worker.get("id") or "")
    file_name = str(worker.get("file") or f"{worker_id}.json")
    read_paths = [str(value) for value in project.get("read_paths", []) if isinstance(value, str)]
    template_id = str(template.get("id") or "")
    read_paths.append(f"templates/pipelines/{template_id}.json")
    return {
        "schema_version": "cento.worker_manifest.v1",
        "id": f"{worker_id}_worker_01",
        "project": str(project.get("id") or ""),
        "template_id": template_id,
        "type": str(template.get("worker_type") or "pipeline_worker"),
        "task_id": worker_id,
        "description": f"{worker.get('description') or worker.get('title') or worker_id} for {project.get('label') or project.get('id') or 'project'}",
        "owned_paths": [f"{project.get('owned_root') or 'workspace/generated'}/{file_name}"],
        "read_paths": read_paths,
        "dependencies": [str(value) for value in worker.get("dependencies", []) if isinstance(value, str)],
        "acceptance": [
            f"{template.get('label') or 'Template'} output is valid",
            "Template parameters are preserved",
            "Only owned paths changed",
        ],
        "validation": {"tier": str(template.get("validation_tier") or "smoke")},
    }


def dev_pipeline_duplicate_template(root: Path, manifest: dict[str, Any], project: dict[str, Any], source_template: dict[str, Any], label_override: str = "") -> dict[str, Any]:
    templates = [item for item in manifest.get("templates", []) if isinstance(item, dict)]
    source_label = str(source_template.get("label") or source_template.get("id") or "Pipeline template")
    label = label_override.strip() if label_override.strip() else f"{source_label} copy"
    base_id = dev_pipeline_slug(label, f"{source_template.get('id') or 'template'}-copy")
    template_id = dev_pipeline_unique_id(templates, base_id)
    copied = deepcopy(source_template)
    copied["id"] = template_id
    copied["label"] = label
    copied["slug"] = template_id
    copied["detail"] = "Editable draft template"
    copied["selected_worker"] = str(copied.get("selected_worker") or "")
    copied_workers = [item for item in copied.get("workers", []) if isinstance(item, dict)]
    for worker in copied_workers:
        worker_id = str(worker.get("id") or "")
        if not worker_id:
            continue
        worker["manifest"] = f"workers/{template_id}_{worker_id}.json"
        worker.setdefault("integration_receipt", f"integration_receipts/{template_id}_{worker_id}.json")
        worker_manifest = dev_pipeline_synthesized_worker_manifest(project, copied, worker)
        write_json_path(dev_pipeline_root_path(root, str(worker["manifest"])), worker_manifest)
    copied["workers"] = copied_workers
    if not copied.get("selected_worker") and copied_workers:
        copied["selected_worker"] = str(copied_workers[0].get("id") or "")
    if isinstance(manifest.get("templates"), list):
        manifest["templates"].append(copied)
    else:
        manifest["templates"] = [copied]
    return copied


def dev_pipeline_stage_element_type(value: Any) -> str:
    raw = dev_pipeline_text(value, "").lower().replace("_", "-").replace(" ", "-")
    aliases = {
        "inputs": "input",
        "operator-input": "input",
        "repo": "worker",
        "repo-discovery": "worker",
        "blueprint": "worker",
        "change-blueprint": "worker",
        "workers": "worker",
        "factory": "integration",
        "factory-step": "integration",
        "integrate": "integration",
        "validator": "validation",
        "validators": "validation",
        "handoff": "evidence",
        "artifact": "evidence",
        "artifacts": "evidence",
    }
    normalized = aliases.get(raw, raw)
    if normalized in {"input", "worker", "integration", "validation", "evidence"}:
        return normalized
    raise AgentWorkAppError(f"Unsupported stage element type: {value}")


def dev_pipeline_stage_kind(value: Any) -> str:
    raw = dev_pipeline_text(value, "").lower().replace("_", "-").replace(" ", "-")
    if raw in {"blueprint", "change-blueprint", "plan"}:
        return "blueprint"
    return "repo"


def dev_pipeline_base_evidence_cards(
    root: Path,
    manifest: dict[str, Any],
    template: dict[str, Any],
    event_total: int,
    budget_spent: float,
    budget_cap: float,
) -> list[dict[str, Any]]:
    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), dict) else {}
    evidence_bundle_rel = str(artifacts.get("evidence_bundle") or "evidence/evidence_bundle.json")
    budget_receipt_rel = str(artifacts.get("budget_receipt") or "evidence/budget_receipt.json")
    pipeline_receipt_rel = str(artifacts.get("pipeline_receipt") or "evidence/pipeline_receipt.json")
    taskstream_evidence_rel = str(artifacts.get("taskstream_evidence") or "evidence/taskstream_evidence.json")
    events_rel = str(artifacts.get("events") or "events.ndjson")
    disabled = {
        dev_pipeline_slug(str(value), "")
        for value in template.get("evidence_disabled", [])
        if str(value).strip()
    }
    base_cards = [
        {"id": "pipeline-receipt", "title": "Pipeline Receipt", "file": "pipeline_receipt.json", "status": title_status(read_json_path(root / pipeline_receipt_rel).get("status") or "completed"), "path": pipeline_receipt_rel, "base": True},
        {"id": "events", "title": "Events Log", "file": "events.ndjson", "status": f"{event_total} events", "path": events_rel, "base": True},
        {"id": "evidence-bundle", "title": "Evidence Bundle", "file": "evidence_bundle.json", "status": "Attached", "path": evidence_bundle_rel, "base": True},
        {"id": "budget", "title": "Budget Receipt", "file": "budget_receipt.json", "status": f"${budget_spent:.2f} of ${budget_cap:.2f}", "path": budget_receipt_rel, "base": True},
        {"id": "taskstream", "title": "Taskstream Evidence", "file": "taskstream_evidence.json", "status": "Review", "path": taskstream_evidence_rel, "base": True},
    ]
    custom_cards = [
        deepcopy(item)
        for item in template.get("evidence_artifacts", [])
        if isinstance(item, dict)
    ]
    return [
        card
        for card in [*base_cards, *custom_cards]
        if dev_pipeline_slug(str(card.get("id") or ""), "") not in disabled
    ]


def dev_pipeline_add_stage_element(root: Path, manifest: dict[str, Any], project: dict[str, Any], template: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    element_type = dev_pipeline_stage_element_type(payload.get("element_type"))
    template_id = str(template.get("id") or "pipeline")
    project_root = str(project.get("owned_root") or "workspace/runs/generic-task/outputs")
    if element_type == "input":
        inputs = dev_pipeline_required_inputs(template.get("required_inputs")) or dev_pipeline_default_required_inputs(template_id)
        element_id = dev_pipeline_unique_id(inputs, "new-input")
        item = {
            "id": element_id,
            "title": "New input",
            "detail": "Describe the operator input this pipeline requires",
            "kind": "details",
            "input_type": "details",
            "format": "markdown",
            "status": "missing",
            "required": True,
        }
        inputs.append(item)
        template["required_inputs"] = dev_pipeline_write_input_manifests(root, manifest, project, template, inputs)
        return {"element_type": element_type, "element_id": element_id, "stage": "input", "title": item["title"]}

    if element_type == "worker":
        workers = [item for item in template.get("workers", []) if isinstance(item, dict)]
        stage = dev_pipeline_stage_kind(payload.get("element_stage"))
        base_id = "blueprint-contract" if stage == "blueprint" else "repo-contract"
        element_id = dev_pipeline_unique_id(workers, base_id)
        file_name = f"{element_id}.json"
        item = {
            "id": element_id,
            "title": "Blueprint contract" if stage == "blueprint" else "Repo contract",
            "file": file_name,
            "description": "Describe the deterministic contract this stage must produce",
            "stage": stage,
            "dependencies": ["repo-context"] if stage == "blueprint" and any(str(worker.get("id") or "") == "repo-context" for worker in workers) else [],
            "manifest": f"workers/{template_id}_{element_id}.json",
            "integration_receipt": f"integration_receipts/{template_id}_{element_id}.json",
        }
        workers.append(item)
        template["workers"] = workers
        write_json_path(dev_pipeline_root_path(root, str(item["manifest"])), dev_pipeline_synthesized_worker_manifest(project, template, item))
        return {"element_type": element_type, "element_id": element_id, "stage": stage, "title": item["title"]}

    if element_type == "integration":
        factory_steps = [item for item in template.get("factory_steps", []) if isinstance(item, dict)]
        element_id = dev_pipeline_unique_id(factory_steps, "new-execution-step")
        dependencies = [str(factory_steps[-1].get("id") or "")] if factory_steps else []
        item = {
            "id": element_id,
            "title": "new_execution_step",
            "file": f"{element_id}.json",
            "status": "queued",
            "mode": "deterministic",
            "dependencies": [dependency for dependency in dependencies if dependency],
            "artifacts": [f"{project_root}/{element_id}.json"],
            "gates": ["Previous dependency receipts are accepted", "No owned-path conflict"],
            "rollback_plan": ["Keep prior receipt until this step applies successfully"],
        }
        factory_steps.append(item)
        template["factory_steps"] = factory_steps
        config = dev_pipeline_integration_config(root, project, template, item, item)
        dev_pipeline_write_factory_step_outputs(root, manifest, project, template, config)
        return {"element_type": element_type, "element_id": element_id, "stage": "integration", "title": item["title"]}

    if element_type == "validation":
        validators = [item for item in template.get("validators", []) if isinstance(item, dict)]
        element_id = dev_pipeline_unique_id(validators, "new-validator")
        item = {
            "id": element_id,
            "title": "New Validator",
            "file": f"{element_id}_receipt.json",
            "receipt": f"validation/{element_id}_receipt.json",
            "config": f"validation/validator_configs/{element_id}.json",
            "mode": "commands",
            "status": "configured",
            "blocking": True,
        }
        validators.append(item)
        template["validators"] = validators
        config = dev_pipeline_validator_config(
            root,
            project,
            template,
            item,
            {
                **item,
                "tier": str(template.get("validation_tier") or "smoke-plus"),
                "summary": "Configure the deterministic checks this validator must run.",
                "commands": ["python3 -m json.tool workspace/runs/dev-pipeline-studio/docs-pages/latest/pipeline_manifest.json"],
                "evidence": ["pipeline_manifest.json"],
                "gates": ["Blocking validator prevents handoff until resolved"],
                "schema_paths": ["pipeline_manifest.json"],
            },
        )
        dev_pipeline_write_validation_outputs(root, manifest, project, template, config)
        return {"element_type": element_type, "element_id": element_id, "stage": "validation", "title": item["title"]}

    evidence_items = [item for item in template.get("evidence_artifacts", []) if isinstance(item, dict)]
    base_ids = {"pipeline-receipt", "events", "evidence-bundle", "budget", "taskstream"}
    element_id = dev_pipeline_unique_id([*evidence_items, *[{"id": base_id} for base_id in base_ids]], "new-evidence")
    item = {
        "id": element_id,
        "title": "New Evidence",
        "file": f"{element_id}.json",
        "status": "Configured",
        "kind": "artifact",
        "path": f"evidence/{element_id}.json",
        "required_sources": ["pipeline_manifest.json", "validation/validation_receipt.json"],
        "publish_policy": "Attach to evidence bundle before Taskstream review",
        "retention_policy": "Keep with the pipeline run artifacts",
        "review_notes": "",
    }
    evidence_items.append(item)
    template["evidence_artifacts"] = evidence_items
    disabled = [dev_pipeline_slug(str(value), "") for value in template.get("evidence_disabled", []) if str(value).strip()]
    template["evidence_disabled"] = [value for value in disabled if value != element_id]
    config = dev_pipeline_evidence_config(root, manifest, project, template, item, item)
    dev_pipeline_write_evidence_outputs(root, manifest, project, template, config)
    return {"element_type": element_type, "element_id": element_id, "stage": "evidence", "title": item["title"]}


def dev_pipeline_delete_stage_element(root: Path, manifest: dict[str, Any], project: dict[str, Any], template: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    element_type = dev_pipeline_stage_element_type(payload.get("element_type"))
    element_id = dev_pipeline_slug(dev_pipeline_text(payload.get("element_id"), ""), "")
    if not element_id:
        raise AgentWorkAppError("element_id is required for delete_element")

    if element_type == "input":
        inputs = [item for item in dev_pipeline_required_inputs(template.get("required_inputs")) if str(item.get("id") or "") != element_id]
        template["required_inputs"] = dev_pipeline_write_input_manifests(root, manifest, project, template, inputs)
    elif element_type == "worker":
        workers = [item for item in template.get("workers", []) if isinstance(item, dict) and str(item.get("id") or "") != element_id]
        template["workers"] = workers
        if str(template.get("selected_worker") or "") == element_id:
            template["selected_worker"] = str(workers[0].get("id") or "") if workers else ""
    elif element_type == "integration":
        template["factory_steps"] = [
            item for item in template.get("factory_steps", [])
            if isinstance(item, dict) and str(item.get("id") or "") != element_id
        ]
    elif element_type == "validation":
        template["validators"] = [
            item for item in template.get("validators", [])
            if isinstance(item, dict) and str(item.get("id") or "") != element_id
        ]
    else:
        evidence_items = [
            item for item in template.get("evidence_artifacts", [])
            if isinstance(item, dict) and dev_pipeline_slug(str(item.get("id") or ""), "") != element_id
        ]
        removed_custom = len(evidence_items) != len([item for item in template.get("evidence_artifacts", []) if isinstance(item, dict)])
        template["evidence_artifacts"] = evidence_items
        if not removed_custom:
            disabled = {
                dev_pipeline_slug(str(value), "")
                for value in template.get("evidence_disabled", [])
                if str(value).strip()
            }
            disabled.add(element_id)
            template["evidence_disabled"] = sorted(value for value in disabled if value)
    return {"element_type": element_type, "element_id": element_id, "deleted": True}


def dev_pipeline_update(payload: dict[str, Any]) -> dict[str, Any]:
    root = DEV_PIPELINE_STUDIO_ROOT
    manifest_path = root / "pipeline_manifest.json"
    manifest = read_json_path(manifest_path)
    if not manifest:
        raise AgentWorkAppError(f"Dev Pipeline Studio manifest not found: {dev_pipeline_relative(manifest_path)}")

    action = str(payload.get("action") or "save").strip() or "save"
    if action not in {"save", "select_worker", "duplicate", "new", "save_input", "save_validation", "run_validation", "save_integration", "save_evidence", "add_element", "delete_element"}:
        raise AgentWorkAppError(f"Unsupported Dev Pipeline Studio action: {action}")

    projects = [item for item in manifest.get("projects", []) if isinstance(item, dict)]
    templates = [item for item in manifest.get("templates", []) if isinstance(item, dict)]
    defaults = manifest.get("defaults") if isinstance(manifest.get("defaults"), dict) else {}
    project_id = str(payload.get("project_id") or defaults.get("project_id") or "").strip()
    template_id = str(payload.get("template_id") or defaults.get("template_id") or "").strip()
    project = dev_pipeline_find(projects, project_id, str(defaults.get("project_id") or ""))
    template = dev_pipeline_find(templates, template_id, str(defaults.get("template_id") or ""))
    if not project or not template:
        raise AgentWorkAppError("A valid project and template are required")
    dev_pipeline_apply_generic_blueprint(template)

    project_payload = payload.get("project") if isinstance(payload.get("project"), dict) else {}
    template_payload = payload.get("template") if isinstance(payload.get("template"), dict) else {}

    if action in {"duplicate", "new"}:
        label_override = ""
        if action == "new":
            label_override = dev_pipeline_text(template_payload.get("label"), "New generic task template")
        elif "label" in template_payload:
            label_override = f"{dev_pipeline_text(template_payload.get('label'), str(template.get('label') or 'Template'))} copy"
        template = dev_pipeline_duplicate_template(root, manifest, project, template, label_override=label_override)
        template_id = str(template.get("id") or "")

    if "label" in project_payload:
        project["label"] = dev_pipeline_text(project_payload.get("label"), str(project.get("label") or ""))
    if "surface" in project_payload:
        project["surface"] = dev_pipeline_text(project_payload.get("surface"), str(project.get("surface") or ""))
    if "surface_value" in project_payload:
        project["surface_value"] = dev_pipeline_text(project_payload.get("surface_value"), str(project.get("surface_value") or ""))
    if "owned_root" in project_payload:
        project["owned_root"] = dev_pipeline_text(project_payload.get("owned_root"), str(project.get("owned_root") or ""))
    if "read_paths" in project_payload or "read_paths_text" in project_payload:
        raw_read_paths = project_payload.get("read_paths", project_payload.get("read_paths_text"))
        project["read_paths"] = dev_pipeline_text_list(raw_read_paths, [str(value) for value in project.get("read_paths", []) if isinstance(value, str)])

    if "label" in template_payload:
        template["label"] = dev_pipeline_text(template_payload.get("label"), str(template.get("label") or ""))
    if "detail" in template_payload:
        template["detail"] = dev_pipeline_text(template_payload.get("detail"), str(template.get("detail") or ""))
    if "description" in template_payload:
        template["description"] = dev_pipeline_text(template_payload.get("description"), str(template.get("description") or ""))
    if "tagline" in template_payload:
        template["tagline"] = dev_pipeline_text(template_payload.get("tagline"), str(template.get("tagline") or ""))
    if "validation_tier" in template_payload:
        template["validation_tier"] = dev_pipeline_text(template_payload.get("validation_tier"), str(template.get("validation_tier") or ""))
    if "risk" in template_payload:
        template["risk"] = dev_pipeline_text(template_payload.get("risk"), str(template.get("risk") or ""))
    if "worker_stage_label" in template_payload:
        template["worker_stage_label"] = dev_pipeline_text(template_payload.get("worker_stage_label"), str(template.get("worker_stage_label") or ""))
    if "factory_stage_label" in template_payload:
        template["factory_stage_label"] = dev_pipeline_text(template_payload.get("factory_stage_label"), str(template.get("factory_stage_label") or ""))
    if "execution_model" in template_payload:
        template["execution_model"] = dev_pipeline_text(template_payload.get("execution_model"), str(template.get("execution_model") or ""))
    if "required_inputs" in template_payload:
        template["required_inputs"] = dev_pipeline_write_input_manifests(
            root,
            manifest,
            project,
            template,
            dev_pipeline_required_inputs(template_payload.get("required_inputs"), template.get("required_inputs")),
        )
    template["budget_spent_usd"] = dev_pipeline_float(template_payload.get("budget_spent_usd"), float(template.get("budget_spent_usd", (manifest.get("budget") or {}).get("spent_usd", 0)) or 0))
    template["budget_cap_usd"] = dev_pipeline_float(template_payload.get("budget_cap_usd"), float(template.get("budget_cap_usd", (manifest.get("budget") or {}).get("cap_usd", 0)) or 0))

    workers = [item for item in template.get("workers", []) if isinstance(item, dict)]
    requested_worker = dev_pipeline_text(template_payload.get("selected_worker"), str(template.get("selected_worker") or ""))
    if action == "select_worker":
        requested_worker = dev_pipeline_text(payload.get("worker_id"), requested_worker)
    if requested_worker and any(str(worker.get("id") or "") == requested_worker for worker in workers):
        template["selected_worker"] = requested_worker
    elif workers and not template.get("selected_worker"):
        template["selected_worker"] = str(workers[0].get("id") or "")

    input_config_payload = payload.get("input_config")
    saved_input_id = ""
    if action == "save_input":
        if not isinstance(input_config_payload, dict):
            raise AgentWorkAppError("input_config is required for save_input")
        existing_inputs = dev_pipeline_required_inputs(template.get("required_inputs")) or dev_pipeline_default_required_inputs(str(template.get("id") or ""))
        normalized_inputs = dev_pipeline_required_inputs([input_config_payload], existing_inputs)
        if not normalized_inputs:
            raise AgentWorkAppError("input_config must include an input title")
        updated_input = normalized_inputs[0]
        saved_input_id = str(updated_input.get("id") or "")
        merged_inputs: list[dict[str, Any]] = []
        replaced = False
        for item in existing_inputs:
            if str(item.get("id") or "") == saved_input_id:
                merged_inputs.append(updated_input)
                replaced = True
            else:
                merged_inputs.append(item)
        if not replaced:
            merged_inputs.append(updated_input)
        template["required_inputs"] = dev_pipeline_write_input_manifests(
            root,
            manifest,
            project,
            template,
            merged_inputs,
        )

    worker_manifest_payload = payload.get("worker_manifest")
    if isinstance(worker_manifest_payload, dict):
        selected_worker_id = str(template.get("selected_worker") or "")
        selected_worker = next((item for item in workers if str(item.get("id") or "") == selected_worker_id), workers[0] if workers else {})
        selected_worker_id = str(selected_worker.get("id") or selected_worker_id)
        if selected_worker_id:
            template["selected_worker"] = selected_worker_id
            manifest_rel = str(selected_worker.get("manifest") or f"workers/{template.get('id')}_{selected_worker_id}.json")
            selected_worker["manifest"] = manifest_rel
            worker_manifest_payload = deepcopy(worker_manifest_payload)
            worker_manifest_payload["schema_version"] = str(worker_manifest_payload.get("schema_version") or "cento.worker_manifest.v1")
            worker_manifest_payload["project"] = str(project.get("id") or "")
            worker_manifest_payload["template_id"] = str(template.get("id") or "")
            worker_manifest_payload["task_id"] = selected_worker_id
            if "validation" not in worker_manifest_payload or not isinstance(worker_manifest_payload.get("validation"), dict):
                worker_manifest_payload["validation"] = {"tier": str(template.get("validation_tier") or "smoke")}
            write_json_path(dev_pipeline_root_path(root, manifest_rel), worker_manifest_payload)

    validation_config_payload = payload.get("validation_config")
    if action in {"save_validation", "run_validation"}:
        if not isinstance(validation_config_payload, dict):
            raise AgentWorkAppError("validation_config is required for validation actions")
        validators = [item for item in template.get("validators", []) if isinstance(item, dict)]
        requested_validator_id = dev_pipeline_slug(dev_pipeline_text(validation_config_payload.get("id"), ""), "validator")
        selected_validator = next((item for item in validators if str(item.get("id") or "") == requested_validator_id), {"id": requested_validator_id})
        config = dev_pipeline_validator_config(root, project, template, selected_validator, validation_config_payload)
        if action == "run_validation":
            config = dev_pipeline_execute_validation(root, config, dev_pipeline_text(payload.get("validation_run_mode"), str(config.get("mode") or "commands")))
        template["validation_tier"] = str(config.get("tier") or template.get("validation_tier") or "")
        dev_pipeline_write_validation_outputs(root, manifest, project, template, config)

    integration_config_payload = payload.get("integration_config")
    if action == "save_integration":
        if not isinstance(integration_config_payload, dict):
            raise AgentWorkAppError("integration_config is required for save_integration")
        workers = [item for item in template.get("workers", []) if isinstance(item, dict)]
        factory_steps = [item for item in template.get("factory_steps", []) if isinstance(item, dict)]
        requested_integration_id = dev_pipeline_slug(dev_pipeline_text(integration_config_payload.get("id"), ""), "integration")
        selected_factory_step = next((item for item in factory_steps if str(item.get("id") or "") == requested_integration_id), None)
        if selected_factory_step is not None:
            config = dev_pipeline_integration_config(root, project, template, selected_factory_step, integration_config_payload)
            dev_pipeline_write_factory_step_outputs(root, manifest, project, template, config)
        else:
            selected_integration = next((item for item in workers if str(item.get("id") or "") == requested_integration_id), {"id": requested_integration_id})
            config = dev_pipeline_integration_config(root, project, template, selected_integration, integration_config_payload)
            dev_pipeline_write_integration_outputs(root, manifest, project, template, config)

    evidence_config_payload = payload.get("evidence_config")
    if action == "save_evidence":
        if not isinstance(evidence_config_payload, dict):
            raise AgentWorkAppError("evidence_config is required for save_evidence")
        config = dev_pipeline_evidence_config(root, manifest, project, template, evidence_config_payload, evidence_config_payload)
        dev_pipeline_write_evidence_outputs(root, manifest, project, template, config)

    mutation: dict[str, Any] = {}
    if action == "add_element":
        mutation = dev_pipeline_add_stage_element(root, manifest, project, template, payload)
    elif action == "delete_element":
        mutation = dev_pipeline_delete_stage_element(root, manifest, project, template, payload)

    defaults = manifest.get("defaults") if isinstance(manifest.get("defaults"), dict) else {}
    defaults["project_id"] = str(project.get("id") or "")
    defaults["template_id"] = str(template.get("id") or "")
    manifest["defaults"] = defaults
    manifest["active_run_id"] = f"{template.get('id')}-{project.get('id')}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    manifest["status"] = "configured" if action in {"save_input", "save_validation", "save_integration", "save_evidence", "add_element", "delete_element"} else "healthy"
    if action == "run_validation":
        manifest["status"] = str(config.get("status") or "configured") if "config" in locals() else "configured"
        manifest["status_detail"] = "Validation tab executed; validator receipts and run results are in sync"
    elif action == "save_input":
        manifest["status_detail"] = "Input contract saved; input manifests are in sync"
    elif action == "save_validation":
        manifest["status_detail"] = "Validation configuration saved; validator manifests and receipts are in sync"
    elif action == "save_integration":
        manifest["status_detail"] = "Integration configuration saved; integration lane manifest and receipts are in sync"
    elif action == "save_evidence":
        manifest["status_detail"] = "Evidence configuration saved; evidence artifact outputs are in sync"
    elif action == "add_element":
        manifest["status_detail"] = f"Added {mutation.get('element_type', 'pipeline')} element {mutation.get('element_id', '')}; pipeline manifest state is in sync"
    elif action == "delete_element":
        manifest["status_detail"] = f"Removed {mutation.get('element_type', 'pipeline')} element {mutation.get('element_id', '')}; pipeline manifest state is in sync"
    else:
        manifest["status_detail"] = "Editable manifest saved; worker contract and pipeline execution metadata are in sync"

    dev_pipeline_apply_generic_blueprint(template)
    write_json_path(manifest_path, manifest)
    dev_pipeline_append_event(
        root,
        manifest,
        f"pipeline_{action}",
        str(project.get("id") or ""),
        str(template.get("id") or ""),
        {
            "selected_worker": str(template.get("selected_worker") or ""),
            "selected_validator": str((validation_config_payload or {}).get("id") or "") if isinstance(validation_config_payload, dict) else "",
            "validation_run_mode": str(payload.get("validation_run_mode") or "") if action == "run_validation" else "",
            "selected_integration": str((integration_config_payload or {}).get("id") or "") if isinstance(integration_config_payload, dict) else "",
            "selected_evidence": str((evidence_config_payload or {}).get("id") or "") if isinstance(evidence_config_payload, dict) else "",
            "selected_input": saved_input_id,
            "mutation": mutation,
        },
    )
    state = dev_pipeline_studio_state(project_id=str(project.get("id") or ""), template_id=str(template.get("id") or ""))
    if mutation:
        state["mutation"] = mutation
    return state


def dev_pipeline_studio_state(project_id: str = "", template_id: str = "") -> dict[str, Any]:
    root = DEV_PIPELINE_STUDIO_ROOT
    manifest_path = root / "pipeline_manifest.json"
    manifest = read_json_path(manifest_path)
    if not manifest:
        raise AgentWorkAppError(f"Dev Pipeline Studio manifest not found: {dev_pipeline_relative(manifest_path)}")

    projects = [item for item in manifest.get("projects", []) if isinstance(item, dict)]
    templates = [item for item in manifest.get("templates", []) if isinstance(item, dict)]
    for item in templates:
        dev_pipeline_apply_generic_blueprint(item)
    defaults = manifest.get("defaults") if isinstance(manifest.get("defaults"), dict) else {}
    project = dev_pipeline_find(projects, project_id, str(defaults.get("project_id") or ""))
    template = dev_pipeline_find(templates, template_id, str(defaults.get("template_id") or ""))
    workers = [item for item in template.get("workers", []) if isinstance(item, dict)]
    raw_factory_steps = template.get("factory_steps")
    factory_steps_explicit = isinstance(raw_factory_steps, list)
    factory_steps = [item for item in raw_factory_steps if isinstance(item, dict)] if factory_steps_explicit else []
    selected_worker_id = str(template.get("selected_worker") or (workers[0].get("id") if workers else ""))
    selected_worker = next((item for item in workers if str(item.get("id") or "") == selected_worker_id), workers[0] if workers else {})
    worker_manifest, worker_manifest_rel = dev_pipeline_worker_manifest(project, template, selected_worker, root)

    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), dict) else {}
    validation_receipt_rel = str(artifacts.get("validation_receipt") or "validation/validation_receipt.json")
    validation_receipt = dev_pipeline_artifact_json(root, validation_receipt_rel)
    evidence_bundle_rel = str(artifacts.get("evidence_bundle") or "evidence/evidence_bundle.json")
    budget_receipt_rel = str(artifacts.get("budget_receipt") or "evidence/budget_receipt.json")
    pipeline_receipt_rel = str(artifacts.get("pipeline_receipt") or "evidence/pipeline_receipt.json")
    taskstream_evidence_rel = str(artifacts.get("taskstream_evidence") or "evidence/taskstream_evidence.json")
    events_rel = str(artifacts.get("events") or "events.ndjson")
    event_total = event_count(root / events_rel)

    budget_spent = float(template.get("budget_spent_usd", (manifest.get("budget") or {}).get("spent_usd", 0)) or 0)
    budget_cap = float(template.get("budget_cap_usd", (manifest.get("budget") or {}).get("cap_usd", 0)) or 0)
    tasks_completed = int(template.get("tasks_completed", len(workers)) or 0)
    tasks_total = int(template.get("tasks_total", max(len(workers), tasks_completed)) or 0)
    execution_model = str(template.get("execution_model") or ("ordered" if str(template.get("id") or "") == "generic-task" else "parallel"))
    worker_stage_label = str(template.get("worker_stage_label") or ("2. Task Execution" if execution_model == "ordered" else "2. Workers (Parallel)"))
    factory_stage_label = str(template.get("factory_stage_label") or "4. Factory Execution")
    worker_count_label = f"{len(workers)} automation contracts" if execution_model == "ordered" else f"{len(workers)} workers"
    required_inputs = dev_pipeline_template_required_inputs(template)
    missing_required_inputs = [
        item for item in required_inputs
        if item.get("required") and str(item.get("status") or "") == "missing"
    ]
    input_count_label = f"{len(missing_required_inputs)} missing / {len(required_inputs)} inputs" if missing_required_inputs else f"{len(required_inputs)} inputs ready"
    validation_status = str(validation_receipt.get("status") or manifest.get("status") or "unknown")
    status_label = "Healthy" if validation_status in {"passed", "healthy", "completed"} else title_status(validation_status, "Unknown")

    worker_cards: list[dict[str, Any]] = []
    integration_cards: list[dict[str, Any]] = []
    for index, worker in enumerate(workers, start=1):
        worker_id = str(worker.get("id") or "")
        file_name = str(worker.get("file") or f"{worker_id}.json")
        receipt_rel = str(worker.get("integration_receipt") or f"integration_receipts/{template.get('id')}_{worker_id}.json")
        integration_config = dev_pipeline_integration_config(root, project, template, worker)
        receipt = dev_pipeline_artifact_json(root, receipt_rel)
        receipt_status = str(integration_config.get("status") or receipt.get("status") or "accepted")
        stage = str(worker.get("stage") or ("blueprint" if worker_id in {"change-blueprint", "plan"} else "repo"))
        dependencies = [str(value) for value in worker.get("dependencies", []) if isinstance(value, str)]
        if dependencies:
            worker_detail = f"{file_name} after {', '.join(dependencies)}"
        elif execution_model == "ordered":
            worker_detail = f"{file_name} step {index}/{len(workers)}"
        else:
            worker_detail = f"{file_name} parallel"
        worker_cards.append(
            {
                "id": worker_id,
                "title": str(worker.get("title") or worker_id),
                "file": file_name,
                "detail": worker_detail,
                "status": "Completed",
                "selected": worker_id == selected_worker_id,
                "stage": stage,
            }
        )

        if not factory_steps and not factory_steps_explicit:
            integration_cards.append(
                {
                    "id": worker_id,
                    "title": str(integration_config.get("title") or f"Integrate: {file_name}"),
                    "file": "integration_receipt.json",
                    "status": title_status(receipt_status, "Accepted"),
                    "path": dev_pipeline_relative(root / receipt_rel) if (root / receipt_rel).exists() else "",
                    "summary": str(integration_config.get("apply_policy") or ""),
                    "mode": str(integration_config.get("mode") or "dependency-order"),
                    "apply_policy": str(integration_config.get("apply_policy") or ""),
                    "conflict_policy": str(integration_config.get("conflict_policy") or ""),
                    "dependencies": [str(value) for value in integration_config.get("dependencies", []) if isinstance(value, str)],
                    "artifacts": [str(value) for value in integration_config.get("artifacts", []) if isinstance(value, str)],
                    "gates": [str(value) for value in integration_config.get("gates", []) if isinstance(value, str)],
                    "rollback_plan": [str(value) for value in integration_config.get("rollback_plan", []) if isinstance(value, str)],
                    "receipt": receipt_rel,
                    "config": dev_pipeline_relative(root / str(integration_config.get("config_path") or f"integration/configs/{worker_id}.json")),
                }
            )

    if factory_steps:
        for step in factory_steps:
            step_id = str(step.get("id") or "")
            file_name = str(step.get("file") or f"{step_id}.json")
            receipt_rel = str(step.get("integration_receipt") or f"integration_receipts/{template.get('id')}_{step_id}.json")
            integration_config = dev_pipeline_integration_config(root, project, template, step)
            receipt = dev_pipeline_artifact_json(root, receipt_rel)
            receipt_status = dev_pipeline_integration_status(step.get("status"), str(integration_config.get("status") or receipt.get("status") or "queued"))
            integration_cards.append(
                {
                    "id": step_id,
                    "title": str(step.get("title") or integration_config.get("title") or step_id),
                    "file": file_name,
                    "status": title_status(receipt_status, "Accepted"),
                    "path": dev_pipeline_relative(root / receipt_rel) if (root / receipt_rel).exists() else "",
                    "summary": str(integration_config.get("apply_policy") or ""),
                    "mode": str(step.get("mode") or integration_config.get("mode") or "deterministic"),
                    "apply_policy": str(integration_config.get("apply_policy") or ""),
                    "conflict_policy": str(integration_config.get("conflict_policy") or ""),
                    "dependencies": [str(value) for value in integration_config.get("dependencies", []) if isinstance(value, str)],
                    "artifacts": [str(value) for value in integration_config.get("artifacts", []) if isinstance(value, str)],
                    "gates": [str(value) for value in integration_config.get("gates", []) if isinstance(value, str)],
                    "rollback_plan": [str(value) for value in integration_config.get("rollback_plan", []) if isinstance(value, str)],
                    "receipt": receipt_rel,
                    "config": dev_pipeline_relative(root / str(integration_config.get("config_path") or f"integration/configs/{step_id}.json")),
                }
            )

    validator_cards: list[dict[str, Any]] = []
    for item in [entry for entry in template.get("validators", []) if isinstance(entry, dict)]:
        receipt_rel = str(item.get("receipt") or "")
        config_rel = str(item.get("config") or f"validation/validator_configs/{item.get('id') or 'validator'}.json")
        config = dev_pipeline_validator_config(root, project, template, item)
        receipt = dev_pipeline_artifact_json(root, receipt_rel)
        receipt_status = str(config.get("status") or receipt.get("status") or item.get("status") or "passed")
        validator_cards.append(
            {
                "id": str(item.get("id") or ""),
                "title": str(config.get("title") or item.get("title") or item.get("id") or "Validator"),
                "file": str(item.get("file") or Path(receipt_rel).name or "receipt.json"),
                "status": title_status(receipt_status, "Passed"),
                "path": dev_pipeline_relative(root / receipt_rel) if receipt_rel else "",
                "summary": str(config.get("summary") or receipt.get("summary") or ""),
                "mode": str(config.get("mode") or item.get("mode") or "commands"),
                "tier": str(config.get("tier") or template.get("validation_tier") or ""),
                "commands": [str(value) for value in config.get("commands", []) if isinstance(value, str)],
                "evidence": [str(value) for value in config.get("evidence", []) if isinstance(value, str)],
                "gates": [str(value) for value in config.get("gates", []) if isinstance(value, str)],
                "schema_paths": [str(value) for value in config.get("schema_paths", []) if isinstance(value, str)],
                "blocking": bool(config.get("blocking", True)),
                "last_run_mode": str(config.get("last_run_mode") or ""),
                "last_run_status": str(config.get("last_run_status") or ""),
                "executed_at": str(config.get("executed_at") or ""),
                "results": config.get("results") if isinstance(config.get("results"), dict) else {},
                "receipt": receipt_rel,
                "config": dev_pipeline_relative(root / config_rel),
            }
        )

    evidence_cards: list[dict[str, Any]] = []
    for item in dev_pipeline_base_evidence_cards(root, manifest, template, event_total, budget_spent, budget_cap):
        config = dev_pipeline_evidence_config(root, manifest, project, template, item)
        config_saved = (root / str(config.get("config_path") or "")).exists()
        evidence_cards.append(
            {
                "id": str(config.get("id") or item.get("id") or ""),
                "title": str(config.get("title") or item.get("title") or ""),
                "file": str(item.get("file") or Path(str(config.get("path") or "")).name),
                "status": title_status(str(config.get("status") or ""), "Configured") if config_saved else str(item.get("status") or title_status(str(config.get("status") or ""), "Configured")),
                "state": str(config.get("status") or "configured"),
                "kind": str(config.get("kind") or ""),
                "path": str(config.get("path") or item.get("path") or ""),
                "config": dev_pipeline_relative(root / str(config.get("config_path") or "")),
                "required_sources": [str(value) for value in config.get("required_sources", []) if isinstance(value, str)],
                "publish_policy": str(config.get("publish_policy") or ""),
                "retention_policy": str(config.get("retention_policy") or ""),
                "review_notes": str(config.get("review_notes") or ""),
                "base": bool(item.get("base", False)),
            }
        )

    return {
        "schema_version": "cento.dev_pipeline_studio_state.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_manifest": dev_pipeline_relative(manifest_path),
        "root": dev_pipeline_relative(root),
        "projects": [
            {
                "id": str(item.get("id") or ""),
                "label": str(item.get("label") or item.get("id") or ""),
                "surface": str(item.get("surface") or ""),
                "surface_value": str(item.get("surface_value") or ""),
                "owned_root": str(item.get("owned_root") or ""),
                "read_paths": [str(value) for value in item.get("read_paths", []) if isinstance(value, str)],
            }
            for item in projects
        ],
        "templates": [
            {
                "id": str(item.get("id") or ""),
                "label": str(item.get("label") or item.get("id") or ""),
                "detail": str(item.get("detail") or ""),
                "description": str(item.get("description") or ""),
                "tagline": str(item.get("tagline") or ""),
                "slug": str(item.get("slug") or item.get("id") or ""),
                "worker_type": str(item.get("worker_type") or "pipeline_worker"),
                "validation_tier": str(item.get("validation_tier") or ""),
                "risk": str(item.get("risk") or ""),
                "budget_spent_usd": float(item.get("budget_spent_usd", 0) or 0),
                "budget_cap_usd": float(item.get("budget_cap_usd", 0) or 0),
                "selected_worker": str(item.get("selected_worker") or ""),
                "execution_model": str(item.get("execution_model") or ("ordered" if str(item.get("id") or "") == "generic-task" else "parallel")),
                "worker_stage_label": str(item.get("worker_stage_label") or ""),
                "factory_stage_label": str(item.get("factory_stage_label") or "4. Factory Execution"),
                "blueprint_version": str(item.get("blueprint_version") or ""),
                "input_manifest": str(item.get("input_manifest") or ""),
                "required_inputs": dev_pipeline_template_required_inputs(item),
                "workers": [
                    {
                        "id": str(worker.get("id") or ""),
                        "title": str(worker.get("title") or worker.get("id") or ""),
                        "file": str(worker.get("file") or ""),
                        "description": str(worker.get("description") or ""),
                        "stage": str(worker.get("stage") or ""),
                        "dependencies": [str(value) for value in worker.get("dependencies", []) if isinstance(value, str)],
                    }
                    for worker in item.get("workers", [])
                    if isinstance(worker, dict)
                ],
                "factory_steps": [
                    {
                        "id": str(step.get("id") or ""),
                        "title": str(step.get("title") or step.get("id") or ""),
                        "file": str(step.get("file") or ""),
                        "status": title_status(str(step.get("status") or "queued"), "Queued"),
                        "dependencies": [str(value) for value in step.get("dependencies", []) if isinstance(value, str)],
                    }
                    for step in item.get("factory_steps", [])
                    if isinstance(step, dict)
                ],
                "validators": [dev_pipeline_validator_config(root, project, item, validator) for validator in item.get("validators", []) if isinstance(validator, dict)],
            }
            for item in templates
        ],
        "selected": {"project_id": str(project.get("id") or ""), "template_id": str(template.get("id") or "")},
        "pipeline": {
            "id": str(manifest.get("id") or ""),
            "run_name": f"{template.get('slug') or template.get('id')}-{project.get('id')}_{str(manifest.get('active_run_id') or '').rsplit('-', 1)[-1]}",
            "status": status_label,
            "status_detail": str(manifest.get("status_detail") or ""),
            "project": str(project.get("label") or project.get("id") or ""),
            "surface": str(project.get("surface") or ""),
            "template": str(template.get("label") or template.get("id") or ""),
            "template_detail": str(template.get("detail") or ""),
            "tasks": f"{tasks_completed} / {tasks_total}",
            "task_state": "Validated",
            "budget": f"${budget_spent:.2f}",
            "budget_detail": f"of ${budget_cap:.2f} budget",
            "elapsed": str(manifest.get("elapsed") or ""),
            "target": str(manifest.get("target") or ""),
            "execution_model": execution_model,
            "worker_stage_label": worker_stage_label,
            "factory_stage_label": factory_stage_label,
            "input_count": input_count_label,
            "worker_count": worker_count_label,
            "integration_count": f"{len(integration_cards)} execution steps" if factory_steps_explicit else f"{len(integration_cards)} integration steps",
            "input_cards": [
                {
                    **deepcopy(item),
                    "id": str(item.get("id") or ""),
                    "title": str(item.get("title") or ""),
                    "file": str(item.get("detail") or item.get("manifest") or ""),
                    "status": title_status(str(item.get("status") or "missing"), "Missing"),
                    "required": bool(item.get("required", True)),
                }
                for item in required_inputs
            ],
            "workers": worker_cards,
            "integration": integration_cards,
            "validators": validator_cards,
            "evidence": evidence_cards,
            "validation": {
                "status": title_status(validation_status, "Passed"),
                "tier": str(template.get("validation_tier") or validation_receipt.get("tier") or ""),
                "receipt": dev_pipeline_relative(root / validation_receipt_rel),
                "checks": len(validation_receipt.get("commands") or []),
                "validator_manifest": dev_pipeline_relative(root / str(artifacts.get("validator_manifest") or "validation/validator_manifest.json")),
            },
            "inspector": {
                "selected_worker": str(selected_worker.get("title") or selected_worker_id),
                "badge": "W1",
                "status": "Completed",
                "manifest": worker_manifest,
                "manifest_path": dev_pipeline_relative(root / worker_manifest_rel) if worker_manifest_rel else "",
                "summary": {
                    "owned_paths": f"{len(worker_manifest.get('owned_paths') or [])} path",
                    "read_paths": f"{len(worker_manifest.get('read_paths') or [])} paths",
                    "dependencies": "None" if not worker_manifest.get("dependencies") else f"{len(worker_manifest.get('dependencies') or [])} dependencies",
                    "validation_tier": str((worker_manifest.get("validation") or {}).get("tier") or template.get("validation_tier") or ""),
                    "risk_level": str(template.get("risk") or ""),
                },
            },
        },
        "artifacts": [
            dev_pipeline_artifact(root, "pipeline_manifest.json"),
            dev_pipeline_artifact(root, str(artifacts.get("workset") or "workset.json")),
            dev_pipeline_artifact(root, validation_receipt_rel),
            dev_pipeline_artifact(root, evidence_bundle_rel),
            dev_pipeline_artifact(root, events_rel),
        ],
    }


def factory_run_list() -> dict[str, Any]:
    root = ROOT_DIR / "workspace" / "runs" / "factory"
    runs = []
    if root.exists():
        for run_dir in sorted((path for path in root.iterdir() if path.is_dir()), key=lambda item: item.stat().st_mtime, reverse=True):
            plan = read_json_path(run_dir / "factory-plan.json")
            if not plan:
                continue
            validation = read_json_path(run_dir / "validation-summary.json")
            evidence_validation = read_json_path(run_dir / "evidence" / "validation-summary.json")
            if evidence_validation:
                validation = evidence_validation
            delivery = read_json_path(run_dir / "delivery-status.json")
            queue = read_json_path(run_dir / "queue" / "queue.json") or read_json_path(run_dir / "queue" / "state.json")
            leases = read_json_path(run_dir / "queue" / "leases.json")
            dispatch = read_json_path(run_dir / "dispatch-plan.json")
            patch_collection = read_json_path(run_dir / "patch-collection-summary.json")
            integration = read_json_path(run_dir / "integration" / "integration-plan.json") or read_json_path(run_dir / "integration-plan.json")
            integration_state = read_json_path(run_dir / "integration" / "integration-state.json")
            integration_branch = read_json_path(run_dir / "integration" / "integration-branch.json")
            applied_patches = read_json_path(run_dir / "integration" / "applied-patches.json")
            rejected_patches = read_json_path(run_dir / "integration" / "rejected-patches.json")
            validation_after_each = read_json_path(run_dir / "integration" / "validation-after-each-patch.json")
            rollback_plan = read_json_path(run_dir / "integration" / "rollback-plan.json")
            merge_readiness = read_json_path(run_dir / "integration" / "merge-readiness.json")
            taskstream_sync = read_json_path(run_dir / "integration" / "taskstream-sync-preview.json")
            release_gates = read_json_path(run_dir / "integration" / "release-gates.json")
            preflight = read_json_path(run_dir / "preflight-summary.json") or read_json_path(run_dir / "preflight.json")
            queue_stats = queue.get("stats") if isinstance(queue.get("stats"), dict) else {}
            delivery_stats = delivery.get("stats") if isinstance(delivery.get("stats"), dict) else {}
            validation_stats = validation.get("stats") if isinstance(validation.get("stats"), dict) else {}
            queue_tasks_raw = queue.get("tasks") or []
            queue_tasks = list(queue_tasks_raw.values()) if isinstance(queue_tasks_raw, dict) else queue_tasks_raw
            queue_tasks = [item for item in queue_tasks if isinstance(item, dict)]
            active_leases = [
                item
                for item in leases.get("leases", [])
                if isinstance(item, dict) and item.get("status") in {"active", "running", "validating", "simulated"}
            ]
            patch_rows = patch_collection.get("patches") if isinstance(patch_collection.get("patches"), list) else []
            validation_checks = validation.get("checks") if isinstance(validation.get("checks"), list) else []
            applied_rows = applied_patches.get("patches") if isinstance(applied_patches.get("patches"), list) else integration_state.get("applied_patches") or []
            rejected_rows = rejected_patches.get("patches") if isinstance(rejected_patches.get("patches"), list) else integration_state.get("rejected_patches") or []
            per_patch_validations = validation_after_each.get("validations") if isinstance(validation_after_each.get("validations"), list) else (integration_state.get("validation_after_each_patch") or {}).get("validations") or []
            taskstream_transitions = taskstream_sync.get("transitions") if isinstance(taskstream_sync.get("transitions"), list) else (integration_state.get("taskstream_sync_preview") or {}).get("transitions") or []
            branch_payload = integration_branch or integration_state.get("branch") or {}
            readiness_payload = merge_readiness or integration_state.get("merge_readiness") or {}
            runs.append(
                {
                    "run_id": run_dir.name,
                    "run_dir": str(run_dir.relative_to(ROOT_DIR)),
                    "package": str(plan.get("package") or ""),
                    "goal": str((plan.get("request") or {}).get("normalized_goal") or ""),
                    "mode": str(plan.get("mode") or ""),
                    "tasks": len(plan.get("tasks") or []),
                    "decision": str(delivery.get("decision") or validation.get("decision") or "incomplete"),
                    "validation_decision": str(validation.get("decision") or ""),
                    "queue": queue_stats,
                    "queue_tasks": queue_tasks[:40],
                    "leases": active_leases[:40],
                    "patch_queue": patch_rows[:40],
                    "dispatch_selected": len(dispatch.get("selected") or []),
                    "integration_decision": str(integration.get("decision") or ""),
                    "integration": {
                        "merge_order": integration.get("merge_order") or [],
                        "candidates": len(integration.get("candidates") or []),
                        "rejected": len(integration.get("rejected") or []),
                        "missing": len(integration.get("missing") or []),
                        "conflicts": len(integration.get("conflicts") or []),
                        "release_gate_status": str(release_gates.get("status") or ""),
                        "state_present": bool(integration_state),
                        "branch": str(branch_payload.get("branch") or ""),
                        "worktree": str(branch_payload.get("worktree") or ""),
                        "branch_status": str(branch_payload.get("status") or ""),
                        "applied_count": len([item for item in applied_rows if isinstance(item, dict)]),
                        "rejected_count": len([item for item in rejected_rows if isinstance(item, dict)]),
                        "validation_after_count": len([item for item in per_patch_validations if isinstance(item, dict)]),
                        "applied_patches": [item for item in applied_rows if isinstance(item, dict)][:40],
                        "rejected_patches": [item for item in rejected_rows if isinstance(item, dict)][:40],
                        "validation_after_each": [item for item in per_patch_validations if isinstance(item, dict)][:40],
                        "merge_readiness": str(readiness_payload.get("decision") or ""),
                        "merge_blockers": readiness_payload.get("blockers") or [],
                        "registry_gate": str(readiness_payload.get("registry_gate") or ""),
                        "rollback_patches": len(rollback_plan.get("patches") or []),
                        "taskstream_transitions": len([item for item in taskstream_transitions if isinstance(item, dict)]),
                    },
                    "validation": {
                        "checks": len(validation_checks),
                        "passed": sum(1 for item in validation_checks if isinstance(item, dict) and item.get("passed")),
                        "decision": str(validation.get("decision") or ""),
                    },
                    "preflight": {
                        "status": "blocked" if preflight.get("blocked") else "passed" if preflight else "not_run",
                        "reasons": preflight.get("reasons") or [],
                    },
                    "ai_calls_used": int(delivery_stats.get("ai_calls_used", validation_stats.get("ai_calls_used", 0)) or 0),
                    "estimated_cost_usd": float(validation.get("estimated_cost_usd", validation_stats.get("estimated_ai_cost_usd", 0)) or 0),
                    "total_duration_ms": float(delivery_stats.get("total_duration_ms", validation_stats.get("total_duration_ms", 0)) or 0),
                    "start_hub": str(run_dir.relative_to(ROOT_DIR) / "start-here.html") if (run_dir / "start-here.html").exists() else "",
                    "implementation_map": str(run_dir.relative_to(ROOT_DIR) / "implementation-map.html") if (run_dir / "implementation-map.html").exists() else "",
                    "release_packet": str(run_dir.relative_to(ROOT_DIR) / "release-packet.md") if (run_dir / "release-packet.md").exists() else "",
                    "release_candidate": str(run_dir.relative_to(ROOT_DIR) / "integration" / "release-candidate.md") if (run_dir / "integration" / "release-candidate.md").exists() else "",
                    "integration_summary": str(run_dir.relative_to(ROOT_DIR) / "integration" / "integration-summary.html") if (run_dir / "integration" / "integration-summary.html").exists() else "",
                    "delivery_status": str(run_dir.relative_to(ROOT_DIR) / "delivery-status.json") if (run_dir / "delivery-status.json").exists() else "",
                    "updated_at": datetime.fromtimestamp(run_dir.stat().st_mtime, timezone.utc).isoformat(),
                }
            )
    delivered = sum(1 for item in runs if item.get("decision") == "delivered")
    return {
        "runs": runs,
        "summary": {
            "total": len(runs),
            "delivered": delivered,
            "incomplete": len(runs) - delivered,
            "ai_calls_used": sum(int(item.get("ai_calls_used") or 0) for item in runs),
            "queued": sum(int((item.get("queue") or {}).get("queued", 0) or 0) for item in runs),
            "waiting": sum(int((item.get("queue") or {}).get("waiting", 0) or 0) for item in runs),
        },
    }


def sync_source() -> str:
    source = os.environ.get(SYNC_SOURCE_ENV, "redmine").strip().lower()
    if source in {"", "redmine"}:
        return "redmine"
    if source in {"disabled", "none", "off", "replacement"}:
        return "disabled"
    raise AgentWorkAppError(f"Unknown {SYNC_SOURCE_ENV}: {source}. Use redmine or disabled.")


def sync_timeout_seconds(default: int = 20) -> int:
    raw = os.environ.get(SYNC_TIMEOUT_ENV, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise AgentWorkAppError(f"{SYNC_TIMEOUT_ENV} must be an integer number of seconds") from exc
    return max(1, value)


def sync_from_agent_work(conn: sqlite3.Connection) -> dict[str, Any]:
    started = datetime.now(timezone.utc).isoformat()
    if sync_source() == "disabled":
        finished = datetime.now(timezone.utc).isoformat()
        return {
            "issues": 0,
            "relocated_local_issues": 0,
            "started_at": started,
            "finished_at": finished,
            "status": "skipped",
            "source": "disabled",
        }
    list_timeout = sync_timeout_seconds()
    detail_timeout = max(1, min(8, list_timeout))
    payload = run_agent_work_json("list", "--all", "--json", backend="redmine", timeout=list_timeout)
    issues = payload.get("issues") or []
    now = datetime.now(timezone.utc).isoformat()
    with conn:
        for issue in issues:
            issue_id = int(issue.get("id"))
            reserve_redmine_issue_id(conn, issue_id)
            description = ""
            try:
                detail = run_agent_work_json("show", str(issue_id), "--json", timeout=detail_timeout, backend="redmine")
                description = str(detail.get("description") or "")
            except Exception:
                description = ""
            conn.execute(
                """
                insert into issues(
                  id, subject, project, tracker, status, priority, assignee, node, agent, role,
                  package, done_ratio, updated_on, description, dispatch, validation_report, closed_on, source, migrated_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'redmine', ?)
                on conflict(id) do update set
                  subject=excluded.subject,
                  project=excluded.project,
                  tracker=excluded.tracker,
                  status=excluded.status,
                  assignee=excluded.assignee,
                  node=excluded.node,
                  agent=excluded.agent,
                  role=excluded.role,
                  package=excluded.package,
                  done_ratio=excluded.done_ratio,
                  updated_on=excluded.updated_on,
                  dispatch=excluded.dispatch,
                  validation_report=excluded.validation_report,
                  closed_on=excluded.closed_on,
                  description=case when excluded.description != '' then excluded.description else issues.description end,
                  migrated_at=excluded.migrated_at
                """,
                (
                    issue_id,
                    issue.get("subject") or "",
                    issue.get("project") or "cento-agent-work",
                    issue.get("tracker") or "Agent Task",
                    issue.get("status") or "Queued",
                    "Normal",
                    issue.get("agent") or "Taskstream Admin",
                    issue.get("node") or "",
                    issue.get("agent") or "",
                    issue.get("role") or "",
                    issue.get("package") or "",
                    int(issue.get("done_ratio") or 0),
                    issue.get("updated_on") or now,
                    description,
                    issue.get("dispatch") or "",
                    issue.get("validation_report") or "",
                    issue.get("closed_on") or (issue.get("updated_on") if str(issue.get("status") or "").lower() == "done" else ""),
                    now,
                ),
            )
            ensure_issue_entity_links(
                conn,
                issue_id=issue_id,
                project=str(issue.get("project") or DEFAULT_PROJECT),
                tracker=str(issue.get("tracker") or "Agent Task"),
                status=str(issue.get("status") or "Queued"),
                assignee=str(issue.get("agent") or issue.get("assignee") or DEFAULT_ASSIGNEE_DISPLAY),
            )
            upsert_issue_custom_values(conn, issue_id, issue_custom_fields_payload(issue))
            ensure_issue_activity(conn, issue)
        relocated = relocate_low_local_issues(conn)
        conn.execute(
            "insert into migration_runs(source, started_at, finished_at, issue_count, status) values (?, ?, ?, ?, ?)",
            ("redmine-agent-work", started, datetime.now(timezone.utc).isoformat(), len(issues), f"ok relocated={relocated}"),
        )
    return {"issues": len(issues), "relocated_local_issues": relocated, "started_at": started, "finished_at": datetime.now(timezone.utc).isoformat()}


def ensure_issue_activity(conn: sqlite3.Connection, issue: dict[str, Any]) -> None:
    issue_id = int(issue.get("id"))
    current = conn.execute("select status from issues where id = ?", (issue_id,)).fetchone()
    updated = issue.get("updated_on") or datetime.now(timezone.utc).isoformat()
    status = issue.get("status") or "Queued"
    old_status = str(current["status"]) if current else ""
    if not current:
        conn.execute(
            "insert into journals(issue_id, created_on, notes, old_status, new_status, source) values (?, ?, ?, ?, ?, 'migration')",
            (issue_id, updated, f"Migrated from the legacy tracker with status {status}.", "", str(status)),
        )
    elif old_status != str(status):
        conn.execute(
            "insert into journals(issue_id, created_on, notes, old_status, new_status, source) values (?, ?, ?, ?, ?, 'migration')",
            (
                issue_id,
                updated,
                f"Status synchronized from {old_status} to {status}.",
                old_status,
                str(status),
            ),
        )
    upsert_issue_custom_values(
        conn,
        issue_id,
        {
            "Validation Report": issue.get("validation_report") or "",
            "Cluster Dispatch": issue.get("dispatch") or "",
            "Cento Work Package": issue.get("package") or "",
            "Agent Node": issue.get("node") or "",
            "Agent Owner": issue.get("agent") or issue.get("assignee") or DEFAULT_ASSIGNEE_DISPLAY,
            "Agent Role": issue.get("role") or "builder",
        },
    )
    if status in {"Review", "Validating", "Done"}:
        validation_path = f"workspace/runs/agent-work/{issue_id}/validation.md"
        add_validation_evidence(
            conn,
            issue_id,
            {
                "label": "validation",
                "path": validation_path,
                "url": "",
                "source": "redmine-sync",
                "note": "Migrated validation evidence link.",
            },
        )


def row_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def relative_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT_DIR))
    except ValueError:
        return str(path)


def issue_validation_state(issue_id: int) -> dict[str, Any]:
    story_path = ROOT_DIR / "workspace" / "runs" / "agent-work" / str(issue_id) / "story.json"
    state: dict[str, Any] = {
        "mode": "unknown",
        "risk": "",
        "no_model_eligible": False,
        "escalation_state": "missing-story",
        "story_manifest": relative_path(story_path),
        "validation_manifest": "",
        "automation_coverage_percent": 0,
        "manual_review_count": 0,
    }
    if not story_path.exists():
        return state
    state["escalation_state"] = "missing-validation"
    try:
        story = json.loads(story_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        state["escalation_state"] = "invalid-story"
        return state
    validation = story.get("validation") if isinstance(story.get("validation"), dict) else {}
    paths = story.get("paths") if isinstance(story.get("paths"), dict) else {}
    state.update(
        {
            "mode": str(validation.get("mode") or "manual-planning"),
            "risk": str(validation.get("risk") or ""),
            "no_model_eligible": bool(validation.get("no_model_eligible")),
            "escalation_triggers": validation.get("escalation_triggers") or [],
        }
    )
    manifest_value = str(validation.get("manifest") or "")
    if not manifest_value:
        run_dir_value = str(paths.get("run_dir") or story_path.parent)
        manifest_value = str(Path(run_dir_value) / "validation.json")
    validation_path = Path(manifest_value)
    if not validation_path.is_absolute():
        validation_path = ROOT_DIR / manifest_value
    state["validation_manifest"] = relative_path(validation_path)
    if not validation_path.exists():
        return state
    try:
        validation_payload = json.loads(validation_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        state["escalation_state"] = "invalid-validation"
        return state
    coverage = validation_payload.get("coverage") if isinstance(validation_payload.get("coverage"), dict) else {}
    manual_review = validation_payload.get("manual_review") if isinstance(validation_payload.get("manual_review"), list) else []
    state["automation_coverage_percent"] = coverage.get("automation_coverage_percent") or 0
    state["manual_review_count"] = len(manual_review)
    unresolved = [
        item for item in manual_review
        if isinstance(item, dict) and str(item.get("status") or "").lower() not in {"accepted", "covered", "waived"}
    ]
    if unresolved:
        state["escalation_state"] = "manual-review"
    elif float(state["automation_coverage_percent"] or 0) < 95:
        state["escalation_state"] = "low-coverage"
    else:
        state["escalation_state"] = "ready"
    return state


def issue_list(
    conn: sqlite3.Connection,
    *,
    status: str | None = "open",
    tracker: str | None = None,
    project: str | None = None,
    assignee: str | None = None,
    query_id: int | None = None,
    search: str | None = None,
    offset: int | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    filters: dict[str, Any] = {}
    if query_id:
        raw_filters = conn.execute("select filters from queries where id = ?", (query_id,)).fetchone()
        if not raw_filters:
            raise AgentWorkAppError(f"Unknown query: {query_id}")
        try:
            parsed_filters = json.loads(raw_filters["filters"])
        except (json.JSONDecodeError, TypeError) as exc:
            raise AgentWorkAppError(f"Invalid query filters: {exc}") from exc
        filters.update(issue_filter_from_raw(parsed_filters if isinstance(parsed_filters, dict) else {}))
    if status is not None:
        filters["status"] = status
    if tracker:
        filters["tracker"] = tracker
    if project:
        filters["project"] = project
    if assignee:
        filters["assignee"] = assignee
    clause, params = filter_clause(filters)
    if search:
        clause = f"{clause} and lower(subject) like ?" if clause else " where lower(subject) like ?"
        params.append(f"%{search.lower()}%")
    total = int(conn.execute(f"select count(*) from issues {clause}", params).fetchone()[0])
    query = f"select * from issues {clause} order by datetime(updated_on) desc, id desc"
    if limit is None or limit <= 0:
        rows = [row_dict(row) for row in conn.execute(query, params)]
        offset = 0
        limit = None
    else:
        if offset is None or offset < 0:
            offset = 0
        rows = [row_dict(row) for row in conn.execute(query + " limit ? offset ?", params + [limit, offset])]
    for item in rows:
        item.update(issue_test_artifact_metadata(item))
        item["validation_state"] = issue_validation_state(int(item["id"]))
    counts = {
        row["tracker"]: row["count"]
        for row in conn.execute(
            f"select tracker, count(*) as count from issues {clause} group by tracker order by tracker",
            params,
        )
    }
    status_counts = {
        row["status"]: row["count"]
        for row in conn.execute(
            f"select status, count(*) as count from issues {clause} group by status order by status",
            params,
        )
    }
    return {
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "issues": rows,
        "counts": counts,
        "status_counts": status_counts,
        "total": total,
        "offset": int(offset or 0),
        "limit": limit,
        "db": str(DB_PATH),
    }


def issue_detail(conn: sqlite3.Connection, issue_id: int) -> dict[str, Any]:
    row = conn.execute("select * from issues where id = ?", (issue_id,)).fetchone()
    if not row:
        raise AgentWorkAppError(f"Issue not found: {issue_id}")
    journals = [row_dict(item) for item in conn.execute("select * from journals where issue_id = ? order by datetime(created_on) desc, id desc", (issue_id,))]
    attachments = [row_dict(item) for item in conn.execute("select * from attachments where issue_id = ? order by id", (issue_id,))]
    test_artifact = issue_test_artifact_metadata(
        row_dict(row),
        attachments=attachments,
        validation_evidences=issue_validation_evidences(conn, issue_id),
        journals=journals,
    )
    issue_payload = {**row_dict(row), **test_artifact}
    issue_payload["validation_state"] = issue_validation_state(issue_id)
    return {
        "issue": issue_payload,
        "journals": journals,
        "attachments": attachments,
        "custom_fields": issue_custom_fields_for_issue(conn, issue_id),
        "validation_evidences": issue_validation_evidences(conn, issue_id),
    }


def artifact_kind(path: str, label: str = "") -> str:
    value = f"{label} {path}".lower()
    suffix = Path(path).suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"} or "screenshot" in value:
        return "screenshot"
    if suffix in {".mp4", ".webm", ".mov"} or "video" in value:
        return "video"
    if suffix in {".json", ".ndjson"} or "json" in value:
        return "output"
    if suffix in {".log", ".txt"} or "log" in value:
        return "logs"
    if suffix in {".md", ".markdown"} or "report" in value or "evidence" in value:
        return "notes"
    return "metadata"


def artifact_url(path: str) -> str:
    if not path:
        return ""
    if path.startswith(("http://", "https://")):
        return path
    return f"/api/artifacts?path={quote(path)}"


TEST_ARTIFACT_PATTERNS = (
    "browser workflow demo",
    "browser workflow",
    "demo issue",
    "demo",
    "test artifact",
    "test issue",
    "fixture",
    "smoke test",
    "smoke",
    "probe",
    "sample",
)

TEST_ARTIFACT_PATH_PATTERNS = (
    "browser-evidence",
)


def issue_test_artifact_metadata(
    issue: dict[str, Any],
    *,
    attachments: list[dict[str, Any]] | None = None,
    validation_evidences: list[dict[str, Any]] | None = None,
    journals: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    haystack_parts = [
        str(issue.get("subject") or ""),
        str(issue.get("description") or ""),
        str(issue.get("package") or ""),
        str(issue.get("validation_report") or ""),
    ]
    if attachments:
        for item in attachments:
            haystack_parts.append(str(item.get("filename") or ""))
            haystack_parts.append(str(item.get("path") or ""))
            haystack_parts.append(str(item.get("evidence_type") or ""))
    if validation_evidences:
        for item in validation_evidences:
            haystack_parts.append(str(item.get("label") or ""))
            haystack_parts.append(str(item.get("path") or ""))
            haystack_parts.append(str(item.get("note") or ""))
    if journals:
        for item in journals[:8]:
            haystack_parts.append(str(item.get("notes") or ""))

    haystack = " \n".join(haystack_parts).lower()
    reasons: list[str] = []
    for pattern in TEST_ARTIFACT_PATTERNS:
        if pattern in haystack:
            reasons.append(f"matched pattern: {pattern}")
    for pattern in TEST_ARTIFACT_PATH_PATTERNS:
        if pattern in haystack:
            reasons.append(f"matched path pattern: {pattern}")

    if "browser" in haystack and "workflow" in haystack:
        reasons.append("browser workflow evidence")
    if "demo" in haystack and ("browser" in haystack or "workflow" in haystack):
        reasons.append("demo browser workflow")
    if "browser-evidence" in haystack:
        reasons.append("browser validation evidence")

    reasons = list(dict.fromkeys(reasons))
    return {
        "test_artifact": bool(reasons),
        "test_artifact_reasons": reasons,
    }


def artifact_payload(label: str, path: str, *, source: str = "local", note: str = "", created_on: str = "") -> dict[str, Any]:
    kind = artifact_kind(path, label)
    return {
        "label": label or Path(path).name or "Evidence",
        "path": path,
        "url": artifact_url(path),
        "kind": kind,
        "source": source,
        "note": note,
        "created_on": created_on,
    }


def read_local_json_artifact(path: str) -> dict[str, Any] | None:
    clean = str(path or "").strip()
    if not clean or clean.startswith(("http://", "https://")):
        return None
    artifact_path = (ROOT_DIR / clean).resolve()
    if ROOT_DIR.resolve() not in artifact_path.parents and artifact_path != ROOT_DIR.resolve():
        return None
    if not artifact_path.exists() or not artifact_path.is_file():
        return None
    try:
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def review_summary_from_validation_report(issue: dict[str, Any]) -> dict[str, Any] | None:
    raw = str(issue.get("validation_report") or "").strip()
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    result = str(payload.get("result_after_gate") or payload.get("result") or "").lower()
    checks = []
    for item in payload.get("checks") or []:
        if not isinstance(item, dict):
            continue
        checks.append(
            {
                "name": str(item.get("name") or "check"),
                "status": "passed" if item.get("ok") else "failed",
                "detail": str(item.get("message") or ""),
                "type": str(item.get("type") or "command"),
            }
        )
    passed = sum(1 for item in checks if item.get("status") == "passed")
    total = len(checks)
    if total:
        summary = f"Validation {'passed' if result == 'pass' else 'needs attention'}: {passed}/{total} checks passed."
    elif result == "pass":
        summary = "Validation passed."
    elif result == "blocked":
        summary = "Validation is blocked."
    elif result == "fail":
        summary = "Validation failed."
    else:
        summary = "Validation report is available."
    return {
        "schema": "cento.review-summary.v1",
        "issue": {"id": issue.get("id"), "subject": issue.get("subject") or ""},
        "result": payload.get("result"),
        "result_after_gate": payload.get("result_after_gate") or payload.get("result"),
        "summary": summary,
        "checks": checks,
        "evidence": [{"type": artifact_kind(str(item), ""), "path": str(item)} for item in payload.get("evidence") or []],
        "recommended_action": "Approve" if result == "pass" else "Needs Fix",
        "review_gate_failures": payload.get("review_gate_failures") or [],
        "agent": payload.get("agent") or issue.get("agent") or issue.get("assignee") or "",
        "node": payload.get("node") or issue.get("node") or "",
        "updated_at": payload.get("updated_at") or issue.get("updated_on") or "",
    }


def review_summary_for_issue(issue: dict[str, Any], artifacts: list[dict[str, Any]]) -> dict[str, Any] | None:
    for artifact in artifacts:
        label = str(artifact.get("label") or "")
        path = str(artifact.get("path") or "")
        if label == "review-summary.json" or Path(path).name == "review-summary.json":
            payload = read_local_json_artifact(path)
            if payload:
                return payload
    return review_summary_from_validation_report(issue)


def issue_artifacts(conn: sqlite3.Connection, issue_id: int) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(label: str, path: str, *, source: str = "local", note: str = "", created_on: str = "") -> None:
        clean = str(path or "").strip()
        if not clean or clean in seen:
            return
        seen.add(clean)
        artifacts.append(artifact_payload(label, clean, source=source, note=note, created_on=created_on))

    for row in conn.execute("select * from attachments where issue_id = ? order by id", (issue_id,)):
        item = row_dict(row)
        add(
            str(item.get("filename") or Path(str(item.get("path") or "")).name),
            str(item.get("path") or ""),
            source="attachment",
            note=str(item.get("evidence_type") or ""),
            created_on=str(item.get("created_on") or ""),
        )

    for item in issue_validation_evidences(conn, issue_id):
        add(
            str(item.get("label") or Path(str(item.get("path") or "")).name or "Validation evidence"),
            str(item.get("url") or item.get("path") or ""),
            source=str(item.get("source") or "validation"),
            note=str(item.get("note") or ""),
            created_on=str(item.get("created_on") or ""),
        )

    candidate_dirs = [
        ROOT_DIR / "workspace" / "runs" / "agent-work" / str(issue_id),
        *sorted((ROOT_DIR / "workspace" / "runs" / "agent-work").glob(f"issue-{issue_id}-*"), reverse=True),
    ]
    for directory in candidate_dirs:
        if not directory.exists() or not directory.is_dir():
            continue
        for path in sorted(directory.iterdir(), key=lambda item: item.stat().st_mtime if item.exists() else 0, reverse=True)[:24]:
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".log", ".txt", ".json", ".md"}:
                continue
            try:
                rel_path = str(path.relative_to(ROOT_DIR))
            except ValueError:
                rel_path = str(path)
            add(path.name, rel_path, source="run-artifact")

    return artifacts


def review_confidence(issue: dict[str, Any], artifacts: list[dict[str, Any]]) -> int:
    score = 58
    kinds = {str(item.get("kind") or "") for item in artifacts}
    if "screenshot" in kinds:
        score += 15
    if "logs" in kinds:
        score += 8
    if "output" in kinds:
        score += 7
    if "notes" in kinds:
        score += 6
    if str(issue.get("validation_report") or "").strip():
        score += 6
    if str(issue.get("role") or "").lower() == "validator":
        score += 4
    return max(1, min(score, 99))


def review_recommendation(confidence: int) -> str:
    if confidence >= 82:
        return "approve"
    if confidence >= 68:
        return "needs_fix"
    return "reject"


def blocker_kind(issue: dict[str, Any], journals: list[dict[str, Any]]) -> str:
    text = " ".join(
        [
            str(issue.get("subject") or ""),
            str(issue.get("description") or ""),
            " ".join(str(item.get("notes") or "") for item in journals[:5]),
        ]
    ).lower()
    if any(token in text for token in ("?", "question", "need answer", "clarify", "ask user", "human")):
        return "question"
    if any(token in text for token in ("run ", "command", "terminal", "sudo", "execute", "shell")):
        return "command"
    if any(token in text for token in ("credential", "password", "token", "device", "iphone", "watch", "lan", "network")):
        return "external"
    return "blocked"


def blocker_summary(issue: dict[str, Any], journals: list[dict[str, Any]]) -> str:
    for journal in journals:
        note = str(journal.get("notes") or "").strip()
        if note:
            return note[:600]
    description = str(issue.get("description") or "").strip()
    if description:
        return description[:600]
    return "No blocker note recorded yet. Use the resolution panel to ask a question, request a command, or requeue when unblocked."


def review_queue(conn: sqlite3.Connection) -> dict[str, Any]:
    rows = [
        row_dict(row)
        for row in conn.execute(
            "select * from issues where lower(status) in ('review', 'blocked') order by case lower(status) when 'blocked' then 0 else 1 end, datetime(updated_on) desc, id desc"
        )
    ]
    items = []
    for issue in rows:
        issue_id = int(issue["id"])
        issue["validation_state"] = issue_validation_state(issue_id)
        artifacts = issue_artifacts(conn, int(issue["id"]))
        journals = [
            row_dict(item)
            for item in conn.execute("select * from journals where issue_id = ? order by datetime(created_on) desc, id desc limit 5", (issue_id,))
        ]
        is_blocked = str(issue.get("status") or "").strip().lower() == "blocked"
        confidence = 0 if is_blocked else review_confidence(issue, artifacts)
        items.append(
            {
                "issue": issue,
                "artifact_count": len(artifacts),
                "primary_artifact": artifacts[0] if artifacts else None,
                "confidence": confidence,
                "recommendation": "blocker" if is_blocked else review_recommendation(confidence),
                "queue_type": "blocker" if is_blocked else "review",
                "blocker": {
                    "kind": blocker_kind(issue, journals),
                    "summary": blocker_summary(issue, journals),
                } if is_blocked else None,
            }
        )
    items.sort(
        key=lambda item: (
            1 if item.get("queue_type") == "blocker" else 0,
            int(item["confidence"]),
            str(item["issue"].get("updated_on") or ""),
        ),
        reverse=True,
    )
    counts = {"approve": 0, "needs_fix": 0, "reject": 0, "pending": 0, "blocker": 0}
    for item in items:
        counts[str(item["recommendation"])] += 1
    counts["pending"] = sum(1 for item in items if item.get("queue_type") == "review")
    return {"items": items, "counts": counts, "total": len(items), "updated_at": now_iso()}


def review_detail(conn: sqlite3.Connection, issue_id: int) -> dict[str, Any]:
    detail = issue_detail(conn, issue_id)
    artifacts = issue_artifacts(conn, issue_id)
    issue = dict(detail["issue"])
    is_blocked = str(issue.get("status") or "").strip().lower() == "blocked"
    confidence = 0 if is_blocked else review_confidence(issue, artifacts)
    return {
        **detail,
        "artifacts": artifacts,
        "review_summary": review_summary_for_issue(issue, artifacts),
        "confidence": confidence,
        "recommendation": "blocker" if is_blocked else review_recommendation(confidence),
        "queue_type": "blocker" if is_blocked else "review",
        "blocker": {
            "kind": blocker_kind(issue, list(detail.get("journals") or [])),
            "summary": blocker_summary(issue, list(detail.get("journals") or [])),
        } if is_blocked else None,
    }


def decide_review(conn: sqlite3.Connection, issue_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    decision = str(payload.get("decision") or "").strip().lower().replace("-", "_")
    note = str(payload.get("note") or "").strip()
    if decision == "approve":
        status = "Done"
        done_ratio = 100
        default_note = "Review cockpit approved deliverable."
    elif decision in {"reject", "needs_fix"}:
        status = "Queued" if decision == "needs_fix" else "Blocked"
        done_ratio = 70 if decision == "needs_fix" else 0
        default_note = "Review cockpit requested changes." if decision == "needs_fix" else "Review cockpit rejected deliverable."
    elif decision in {"question", "command"}:
        status = "Blocked"
        done_ratio = 0
        default_note = "Review cockpit requested an answer." if decision == "question" else "Review cockpit requested an operator command."
    elif decision in {"unblock", "requeue"}:
        status = "Queued"
        done_ratio = 0
        default_note = "Review cockpit marked blocker resolved and requeued work."
    else:
        raise AgentWorkAppError("decision must be approve, reject, needs_fix, question, command, or unblock")
    return update_local_issue(
        conn,
        issue_id,
        {
            "status": status,
            "done_ratio": done_ratio,
            "note": note or default_note,
            "assignee": payload.get("assignee") or "review cockpit",
        },
    )


def create_local_issue(conn: sqlite3.Connection, payload: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    subject = str(payload.get("subject") or "").strip()
    if not subject:
        raise AgentWorkAppError("subject is required")
    row = conn.execute("select coalesce(max(id), 0) + 1 as id from issues").fetchone()
    issue_id = int(row["id"])
    project = str(payload.get("project") or DEFAULT_PROJECT)
    tracker = str(payload.get("tracker") or "Agent Task")
    status = str(payload.get("status") or "Queued")
    assignee = str(payload.get("assignee") or payload.get("agent") or "local operator")
    role = str(payload.get("role") or "builder")
    package = str(payload.get("package") or "default")
    now = now_iso()
    with conn:
        conn.execute(
            """
            insert into issues(
              id, subject, project, tracker, status, priority, assignee, node, agent, role,
              package, done_ratio, updated_on, description, source, migrated_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'local', ?)
            """,
            (
                issue_id,
                subject,
                project,
                tracker,
                status,
                payload.get("priority") or "Normal",
                assignee,
                payload.get("node") or "",
                payload.get("agent") or "",
                role,
                package,
                int(payload.get("done_ratio") or 0),
                now,
                payload.get("description") or "",
                now,
            ),
        )
        ensure_issue_entity_links(conn, issue_id=issue_id, project=project, tracker=tracker, status=status, assignee=assignee)
        upsert_issue_custom_values(conn, issue_id, issue_custom_fields_payload(payload))
        conn.execute(
            "insert into journals(issue_id, author, created_on, notes, new_status, source) values (?, ?, ?, ?, ?, 'local')",
            (issue_id, assignee, now, "Created in Cento Taskstream.", status),
        )
    return issue_detail(conn, issue_id)


def update_local_issue(conn: sqlite3.Connection, issue_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    current = conn.execute("select * from issues where id = ?", (issue_id,)).fetchone()
    if not current:
        raise AgentWorkAppError(f"Issue not found: {issue_id}")
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
        "done_ratio",
        "description",
    }
    updates = {key: payload[key] for key in allowed if key in payload}
    custom_fields = issue_custom_fields_payload(payload)
    if not updates and not custom_fields and not payload.get("note"):
        return issue_detail(conn, issue_id)
    old_status = str(current["status"])
    now = datetime.now(timezone.utc).isoformat()
    with conn:
        if updates:
            assignments = ", ".join(f"{key} = ?" for key in updates)
            values = list(updates.values())
            values.extend([now, issue_id])
            conn.execute(f"update issues set {assignments}, updated_on = ? where id = ?", values)
        if "status" in updates and str(updates["status"]) != old_status:
            conn.execute(
                "insert into journals(issue_id, author, created_on, notes, old_status, new_status, source) values (?, ?, ?, ?, ?, ?, 'local')",
                (
                    issue_id,
                    payload.get("assignee") or current["assignee"] or "local operator",
                    now,
                    payload.get("note") or f"Status changed from {old_status} to {updates['status']}.",
                    old_status,
                    str(updates["status"]),
                ),
            )
        elif payload.get("note"):
            add_local_journal(conn, issue_id, {"notes": payload.get("note"), "author": payload.get("assignee") or current["assignee"]})
        if custom_fields:
            upsert_issue_custom_values(conn, issue_id, custom_fields)
        ensure_issue_entity_links(
            conn,
            issue_id=issue_id,
            project=str(updates.get("project", current["project"])),
            tracker=str(updates.get("tracker", current["tracker"])),
            status=str(updates.get("status", current["status"])),
            assignee=str(updates.get("assignee", current["assignee"])),
        )
    return issue_detail(conn, issue_id)


def add_local_journal(conn: sqlite3.Connection, issue_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    if not conn.execute("select 1 from issues where id = ?", (issue_id,)).fetchone():
        raise AgentWorkAppError(f"Issue not found: {issue_id}")
    now = datetime.now(timezone.utc).isoformat()
    with conn:
        conn.execute(
            "insert into journals(issue_id, author, created_on, notes, old_status, new_status, source) values (?, ?, ?, ?, ?, ?, 'local')",
            (
                issue_id,
                payload.get("author") or "local operator",
                now,
                payload.get("notes") or payload.get("note") or "",
                payload.get("old_status") or "",
                payload.get("new_status") or "",
            ),
        )
        conn.execute("update issues set updated_on = ? where id = ?", (now, issue_id))
    return issue_detail(conn, issue_id)


def add_local_attachment(conn: sqlite3.Connection, issue_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    if not conn.execute("select 1 from issues where id = ?", (issue_id,)).fetchone():
        raise AgentWorkAppError(f"Issue not found: {issue_id}")
    filename = str(payload.get("filename") or "").strip()
    if not filename:
        raise AgentWorkAppError("filename is required")
    now = now_iso()
    with conn:
        conn.execute(
            """
            insert into attachments(issue_id, filename, size, path, created_on, mime_type, checksum, evidence_type)
            values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                issue_id,
                filename,
                payload.get("size") or "",
                payload.get("path") or "",
                now,
                payload.get("mime_type") or "",
                payload.get("checksum") or "",
                payload.get("evidence_type") or "",
            ),
        )
        conn.execute("update issues set updated_on = ? where id = ?", (now, issue_id))
    return issue_detail(conn, issue_id)


def safe_static_path(raw_path: str) -> Path:
    route = raw_path.split("?", 1)[0].split("#", 1)[0]
    app_routes = {
        "/",
        "/review",
        "/cluster",
        "/consulting",
        "/factory",
        "/docs",
        "/research-center",
        "/software-delivery-hub",
        "/dev-pipeline-studio",
        "/codebase-intelligence",
        "/issues",
    }
    if route in ("",) or route in app_routes or route.startswith("/issues/"):
        route = "/index.html"
    path = (TEMPLATE_DIR / route.lstrip("/")).resolve()
    template_root = TEMPLATE_DIR.resolve()
    if template_root not in path.parents and path != template_root:
        raise AgentWorkAppError("Invalid static path.")
    return path


def make_handler(db_path: Path) -> type[BaseHTTPRequestHandler]:
    class AgentWorkHandler(BaseHTTPRequestHandler):
        server_version = "cento-agent-work-app/0.1"

        def log_message(self, fmt: str, *args: object) -> None:
            print(f"{self.address_string()} - {fmt % args}", file=sys.stderr)

        def send_json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, indent=2, default=str).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0:
                return {}
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            return payload if isinstance(payload, dict) else {}

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            try:
                if parsed.path in {"/health", "/api/health"}:
                    self.send_json(
                        200,
                        {
                            "status": "ok",
                            "pid": os.getpid(),
                            "port": getattr(self.server, "server_port", 0),
                            "url": f"http://{self.server.server_address[0]}:{getattr(self.server, 'server_port', 0)}/",
                            "db": str(db_path),
                        },
                    )
                    return
                if parsed.path == "/api/projects":
                    with connect(db_path) as conn:
                        init_db(conn)
                        self.send_json(200, {"projects": list_reference(conn, "projects", include_counts=True)})
                    return
                if parsed.path == "/api/trackers":
                    with connect(db_path) as conn:
                        init_db(conn)
                        self.send_json(200, {"trackers": list_reference(conn, "trackers", include_counts=True)})
                    return
                if parsed.path == "/api/statuses":
                    with connect(db_path) as conn:
                        init_db(conn)
                        self.send_json(200, {"statuses": list_reference(conn, "statuses", include_counts=True)})
                    return
                if parsed.path == "/api/assignees":
                    with connect(db_path) as conn:
                        init_db(conn)
                        self.send_json(200, {"assignees": list_reference(conn, "assignees", include_counts=True)})
                    return
                if parsed.path == "/api/custom_fields":
                    with connect(db_path) as conn:
                        init_db(conn)
                        self.send_json(200, {"custom_fields": list_reference(conn, "issue_custom_fields")})
                    return
                if parsed.path == "/api/queries":
                    with connect(db_path) as conn:
                        init_db(conn)
                        self.send_json(200, {"queries": list_queries(conn)})
                    return
                if parsed.path.startswith("/api/queries/"):
                    query_id = int(parsed.path.rsplit("/", 1)[-1])
                    with connect(db_path) as conn:
                        init_db(conn)
                        row = conn.execute("select * from queries where id = ?", (query_id,)).fetchone()
                        if not row:
                            self.send_json(404, {"error": f"Query not found: {query_id}"})
                            return
                        self.send_json(200, {"query": row_dict(row)})
                    return
                if parsed.path == "/api/issues":
                    query = parse_qs(parsed.query)
                    with connect(db_path) as conn:
                        init_db(conn)
                        status_value = (query.get("status") or ["open"])[0]
                        search = (query.get("search") or query.get("q") or [None])[0]
                        try:
                            offset = int((query.get("offset") or [0])[0])
                        except (ValueError, TypeError):
                            offset = 0
                        try:
                            limit = int((query.get("limit") or [0])[0])
                        except (ValueError, TypeError):
                            limit = None
                        if limit is not None and limit <= 0:
                            limit = None
                        if not limit and "page" in query and "per_page" in query:
                            try:
                                page = max(1, int((query.get("page") or [1])[0]))
                                per_page = max(1, int((query.get("per_page") or [25])[0]))
                            except (TypeError, ValueError):
                                limit = None
                                offset = 0
                            else:
                                limit = per_page
                                offset = (page - 1) * per_page
                        query_id = None
                        if query.get("query"):
                            try:
                                query_id = int((query.get("query") or [None])[0])
                            except (TypeError, ValueError) as exc:
                                raise AgentWorkAppError("query must be an integer") from exc
                        self.send_json(
                            200,
                            issue_list(
                                conn,
                                status=status_value,
                                tracker=(query.get("tracker") or [None])[0],
                                project=(query.get("project") or [None])[0],
                                assignee=(query.get("assignee") or [None])[0],
                                query_id=query_id,
                                search=search,
                                offset=offset,
                                limit=limit,
                            ),
                        )
                    return
                if parsed.path == "/api/runs":
                    self.send_json(200, run_list())
                    return
                if parsed.path == "/api/factory":
                    self.send_json(200, factory_run_list())
                    return
                if parsed.path == "/api/dev-pipeline-studio":
                    query = parse_qs(parsed.query)
                    project_id = str((query.get("project") or [""])[0])
                    template_id = str((query.get("template") or [""])[0])
                    self.send_json(200, dev_pipeline_studio_state(project_id=project_id, template_id=template_id))
                    return
                if parsed.path == "/api/review":
                    with connect(db_path) as conn:
                        init_db(conn)
                        self.send_json(200, review_queue(conn))
                    return
                if parsed.path.startswith("/api/review/"):
                    issue_id = int(parsed.path.rsplit("/", 1)[-1])
                    with connect(db_path) as conn:
                        init_db(conn)
                        self.send_json(200, review_detail(conn, issue_id))
                    return
                if parsed.path == "/api/artifacts":
                    query = parse_qs(parsed.query)
                    raw_artifact = str((query.get("path") or [""])[0])
                    if not raw_artifact:
                        self.send_json(400, {"error": "path is required"})
                        return
                    if raw_artifact.startswith(("http://", "https://")):
                        self.send_json(400, {"error": "remote artifact fetch is not supported"})
                        return
                    artifact_path = (ROOT_DIR / raw_artifact).resolve()
                    if ROOT_DIR.resolve() not in artifact_path.parents and artifact_path != ROOT_DIR.resolve():
                        self.send_json(403, {"error": "artifact path is outside repository"})
                        return
                    if not artifact_path.exists() or not artifact_path.is_file():
                        self.send_json(404, {"error": "artifact not found"})
                        return
                    body = artifact_path.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", mimetypes.guess_type(artifact_path.name)[0] or "text/plain; charset=utf-8")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                if parsed.path.startswith("/api/issues/"):
                    with connect(db_path) as conn:
                        init_db(conn)
                        issue_id = int(parsed.path.rsplit("/", 1)[-1])
                        if parsed.path.endswith("/validation_evidences"):
                            self.send_json(200, {"validation_evidences": issue_validation_evidences(conn, issue_id)})
                        else:
                            self.send_json(200, issue_detail(conn, issue_id))
                    return
                if parsed.path == "/api/sync":
                    with connect(db_path) as conn:
                        init_db(conn)
                        self.send_json(200, sync_from_agent_work(conn))
                    return
                if parsed.path == "/api/codebase-intelligence":
                    import codebase_intelligence as ci
                    self.send_json(200, ci.inventory())
                    return
                if parsed.path == "/api/codebase-intelligence/graph":
                    import codebase_intelligence as ci
                    self.send_json(200, ci.build_graph())
                    return
                if parsed.path == "/api/codebase-intelligence/inspect":
                    import codebase_intelligence as ci
                    query = parse_qs(parsed.query)
                    file_path = str((query.get("path") or [""])[0])
                    if not file_path:
                        self.send_json(400, {"error": "path query parameter is required"})
                        return
                    result = ci.inspect_file(file_path)
                    status = 404 if "error" in result and result.get("error") in ("file not found", "path is not a file") else (403 if "error" in result and "outside" in str(result.get("error")) else 200)
                    self.send_json(status, result)
                    return
                path = safe_static_path(self.path)
                if not path.exists() or not path.is_file():
                    self.send_json(404, {"error": "Not found"})
                    return
                body = path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception as exc:
                self.send_json(500, {"error": str(exc)})

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            try:
                payload = self.read_json()
                if parsed.path == "/api/dev-pipeline-studio":
                    self.send_json(200, dev_pipeline_update(payload))
                    return
                with connect(db_path) as conn:
                    init_db(conn)
                    if parsed.path == "/api/issues":
                        self.send_json(201, create_local_issue(conn, payload))
                        return
                    if parsed.path == "/api/queries":
                        query_name = str(payload.get("name") or "").strip()
                        if not query_name:
                            raise AgentWorkAppError("query name is required")
                        raw_filters = payload.get("filters")
                        if isinstance(raw_filters, dict):
                            filters = json.dumps(raw_filters, sort_keys=True, default=str)
                        else:
                            filters = str(raw_filters or "{}")
                        is_default = 1 if bool(payload.get("is_default")) else 0
                        query_id = ensure_query(conn, query_name, filters, is_default)
                        row = conn.execute("select * from queries where id = ?", (query_id,)).fetchone()
                        if not row:
                            raise AgentWorkAppError("Unable to persist query")
                        self.send_json(201, {"query": row_dict(row)})
                        return
                    if parsed.path.startswith("/api/issues/") and parsed.path.endswith("/journals"):
                        if parsed.path.count("/") != 4:
                            raise AgentWorkAppError("invalid issues journals endpoint")
                        issue_id = int(parsed.path.split("/")[-2])
                        self.send_json(201, add_local_journal(conn, issue_id, payload))
                        return
                    if parsed.path.startswith("/api/issues/") and parsed.path.endswith("/attachments"):
                        if parsed.path.count("/") != 4:
                            raise AgentWorkAppError("invalid issues attachments endpoint")
                        issue_id = int(parsed.path.split("/")[-2])
                        self.send_json(201, add_local_attachment(conn, issue_id, payload))
                        return
                    if parsed.path.startswith("/api/issues/") and parsed.path.endswith("/validation_evidences"):
                        if parsed.path.count("/") != 4:
                            raise AgentWorkAppError("invalid issues validation_evidences endpoint")
                        issue_id = int(parsed.path.split("/")[-2])
                        self.send_json(201, add_validation_evidence(conn, issue_id, payload))
                        return
                    if parsed.path.startswith("/api/review/") and parsed.path.endswith("/decision"):
                        if parsed.path.count("/") != 4:
                            raise AgentWorkAppError("invalid review decision endpoint")
                        issue_id = int(parsed.path.split("/")[-2])
                        self.send_json(200, decide_review(conn, issue_id, payload))
                        return
                self.send_json(404, {"error": "Not found"})
            except Exception as exc:
                self.send_json(500, {"error": str(exc)})

        def do_PATCH(self) -> None:
            parsed = urlparse(self.path)
            try:
                if parsed.path.count("/") == 3 and parsed.path.startswith("/api/issues/"):
                    issue_id = int(parsed.path.rsplit("/", 1)[-1])
                    with connect(db_path) as conn:
                        init_db(conn)
                        self.send_json(200, update_local_issue(conn, issue_id, self.read_json()))
                    return
                self.send_json(404, {"error": "Not found"})
            except Exception as exc:
                self.send_json(500, {"error": str(exc)})

    return AgentWorkHandler


def main() -> int:
    args = parse_args()
    command = getattr(args, "command", None)
    if command in {None, "serve"}:
        return run_server(args)
    if command == "start":
        args.exact_port = True
        return command_start(args)
    if command == "stop":
        return command_stop(args)
    if command == "status":
        return command_status(args)
    if command == "import-redmine":
        return command_import_redmine(args)
    if command == "install-sync":
        return command_install_sync(args)
    raise AgentWorkAppError(f"Unknown command: {command}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AgentWorkAppError as exc:
        print(f"agent-work-app: {exc}", file=sys.stderr)
        raise SystemExit(1)
