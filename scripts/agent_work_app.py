#!/usr/bin/env python3
from __future__ import annotations

import argparse
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


def factory_run_list() -> dict[str, Any]:
    root = ROOT_DIR / "workspace" / "runs" / "factory"
    runs = []
    if root.exists():
        for run_dir in sorted((path for path in root.iterdir() if path.is_dir()), key=lambda item: item.stat().st_mtime, reverse=True):
            plan = read_json_path(run_dir / "factory-plan.json")
            if not plan:
                continue
            validation = read_json_path(run_dir / "validation-summary.json")
            delivery = read_json_path(run_dir / "delivery-status.json")
            queue = read_json_path(run_dir / "queue" / "state.json")
            dispatch = read_json_path(run_dir / "dispatch-plan.json")
            integration = read_json_path(run_dir / "integration-plan.json")
            queue_stats = queue.get("stats") if isinstance(queue.get("stats"), dict) else {}
            delivery_stats = delivery.get("stats") if isinstance(delivery.get("stats"), dict) else {}
            validation_stats = validation.get("stats") if isinstance(validation.get("stats"), dict) else {}
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
                    "dispatch_selected": len(dispatch.get("selected") or []),
                    "integration_decision": str(integration.get("decision") or ""),
                    "ai_calls_used": int(delivery_stats.get("ai_calls_used", validation_stats.get("ai_calls_used", 0)) or 0),
                    "total_duration_ms": float(delivery_stats.get("total_duration_ms", validation_stats.get("total_duration_ms", 0)) or 0),
                    "start_hub": str(run_dir.relative_to(ROOT_DIR) / "start-here.html") if (run_dir / "start-here.html").exists() else "",
                    "implementation_map": str(run_dir.relative_to(ROOT_DIR) / "implementation-map.html") if (run_dir / "implementation-map.html").exists() else "",
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
    if route in ("", "/") or route in {"/review", "/cluster", "/consulting", "/factory", "/docs", "/research-center"} or route.startswith("/issues/"):
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
