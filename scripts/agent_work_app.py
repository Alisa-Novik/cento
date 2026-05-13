#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import json
import mimetypes
import os
import re
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
from datetime import datetime, timedelta, timezone
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
DEV_PIPELINE_EXECUTION_LOCK = threading.Lock()
DEV_PIPELINE_EXECUTION_MIN_STEP_SECONDS = float(os.environ.get("CENTO_PIPELINE_EXECUTION_MIN_STEP_SECONDS", "3.0"))
HARD_PROREQ_PROJECT_ID = "hard-proreq-project"
HARD_PROREQ_TEMPLATE_ID = "hard-proreq-task"
PROREQ_LIGHT_PROJECT_ID = "proreq-light-project"
PROREQ_LIGHT_TEMPLATE_ID = "proreq-light-task"
MULTIPIPELINE_PROJECT_ID = "multipipeline-proreq-project"
MULTIPIPELINE_TEMPLATE_ID = "multipipeline-proreq-chain"
PARALLEL_PIPELINE_PROJECT_ID = "parallel-pipeline-project"
PARALLEL_PIPELINE_TEMPLATE_ID = "parallel-pipeline"
PATCH_SWARM_PROJECT_ID = "patch-swarm-project"
PATCH_SWARM_TEMPLATE_ID = "patch-swarm"
PARALLEL_PIPELINE_FIXTURE_TARGET_PATHS = [
    "docs/agent-run-ledger.md",
    "docs/agent-work-coordinator-lane.md",
    "docs/agent-work-deliverables-hub.md",
    "docs/agent-work-docs-evidence-lane.md",
    "docs/agent-work-runtimes.md",
    "docs/agent-work-screenshot-runner.md",
    "docs/agent-work-story-manifest.md",
    "docs/agent-work-validator-lane.md",
    "docs/cento-build.md",
    "docs/cento-workset.md",
    "standards/README.md",
    "standards/mcp.md",
]
DEFAULT_DEV_PIPELINE_PROJECT_ID = HARD_PROREQ_PROJECT_ID
DEFAULT_DEV_PIPELINE_TEMPLATE_ID = HARD_PROREQ_TEMPLATE_ID
HEALTH_PATH = "/health"
SYNC_CRON_BEGIN = "# >>> cento agent-work-app sync >>>"
SYNC_CRON_END = "# <<< cento agent-work-app sync <<<"
SYNC_SOURCE_ENV = "CENTO_AGENT_WORK_APP_SYNC_SOURCE"
SYNC_TIMEOUT_ENV = "CENTO_AGENT_WORK_APP_SYNC_TIMEOUT_SECONDS"


def load_local_cento_secrets() -> None:
    config_root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    secrets_path = Path(os.environ.get("CENTO_SECRETS_ENV", config_root / "cento" / "secrets.env"))
    try:
        lines = secrets_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    allowed = {
        "OPENAI_API_KEY",
        "CENTO_OPENAI_PLANNER_MODEL",
        "CENTO_OPENAI_WORKER_MODEL",
        "CENTO_OPENAI_REVIEWER_MODEL",
        "CENTO_OPENAI_PRO_MODEL",
        "CENTO_OPENAI_IMAGE_MODEL",
    }
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[7:].lstrip()
        if "=" not in stripped:
            continue
        key, raw_value = stripped.split("=", 1)
        key = key.strip()
        if key not in allowed or os.environ.get(key):
            continue
        try:
            parsed = shlex.split(raw_value, posix=True)
        except ValueError:
            parsed = [raw_value.strip().strip("\"'")]
        os.environ[key] = parsed[0] if parsed else ""


load_local_cento_secrets()


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


def read_event_rows(path: Path, limit: int = 120) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return rows
    for line in lines[-limit:]:
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def parse_iso_datetime(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = f"{raw[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def format_run_time(value: datetime | None, include_date: bool = True) -> str:
    if value is None:
        return ""
    local = value.astimezone()
    if include_date:
        text = local.strftime("%b %d, %Y %I:%M:%S %p")
    else:
        text = local.strftime("%I:%M:%S %p")
    return text.replace(" 0", " ")


def duration_seconds_from_label(value: Any, fallback: int) -> int:
    text = str(value or "").strip().lower()
    if not text:
        return fallback
    total = 0
    saw_number = False
    for token in text.replace(",", " ").split():
        number = "".join(char for char in token if char.isdigit())
        if not number:
            continue
        saw_number = True
        amount = int(number)
        if "h" in token:
            total += amount * 3600
        elif "m" in token:
            total += amount * 60
        else:
            total += amount
    return total if saw_number else fallback


def duration_label(seconds: int) -> str:
    seconds = max(0, int(seconds or 0))
    minutes, remainder = divmod(seconds, 60)
    if minutes:
        return f"{minutes}m {remainder:02d}s"
    return f"{remainder}s"


def file_size_label(path: Path) -> str:
    try:
        size = path.stat().st_size
    except OSError:
        return "missing"
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    if size >= 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size} B"


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
PIPELINE_RUN_INPUT_TYPES = {"text", "questionnaire", "path", "image", "details", "evidence"}
PIPELINE_RUN_SCHEMA_VERSION = "cento.pipeline_run_request.v1"


def dev_pipeline_input_source(value: Any, fallback: str = "user") -> str:
    source = dev_pipeline_text(value, fallback).lower().replace("_", "-").replace(" ", "-")
    aliases = {
        "operator": "user",
        "manual": "user",
        "generated": "auto",
        "automation": "auto",
        "automated": "auto",
    }
    source = aliases.get(source, source)
    return source if source in {"user", "auto"} else fallback


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
        if status not in {"provided", "configured", "missing", "optional", "muted", "skipped", "blocking-config"}:
            status = "missing"
        item_id = dev_pipeline_slug(dev_pipeline_text(item.get("id"), title), f"input-{index}")
        kind = dev_pipeline_input_type(item.get("kind", item.get("input_type", item.get("type"))), dev_pipeline_inferred_input_type(item_id, title))
        source = dev_pipeline_input_source(item.get("source", item.get("automation_source")), "user")
        automation = dev_pipeline_text(item.get("automation", item.get("automation_source")), "")
        normalized = {
            "id": item_id,
            "title": title,
            "detail": dev_pipeline_text(item.get("detail"), ""),
            "kind": kind,
            "input_type": kind,
            "source": source,
            "automation": automation,
            "automation_source": automation,
            "muted": bool(item.get("muted", status == "muted")),
            "blocking": bool(item.get("blocking", not bool(item.get("muted", status == "muted")))),
            "format": dev_pipeline_text(item.get("format"), ""),
            "status": status,
            "required": bool(item.get("required", status != "optional")),
            "advanced": bool(item.get("advanced", False)),
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


def dev_pipeline_parallel_project_defaults() -> dict[str, Any]:
    return {
        "id": PARALLEL_PIPELINE_PROJECT_ID,
        "label": "Parallel Pipeline Project",
        "surface": "Cento workset parallel execution",
        "surface_value": PARALLEL_PIPELINE_TEMPLATE_ID,
        "owned_root": "workspace/runs/parallel-pipeline/outputs",
        "read_paths": [
            "AGENTS.md",
            "README.md",
            "scripts/**",
            "templates/agent-work-app/**",
            "docs/**",
            "tests/**",
            "data/tools.json",
            ".cento/api_workers.yaml",
        ],
    }


def dev_pipeline_parallel_blueprint_defaults() -> dict[str, Any]:
    return {
        "id": PARALLEL_PIPELINE_TEMPLATE_ID,
        "label": "Parallel workset pipeline",
        "detail": "Contract-first parallel workers with one serialized integration lane",
        "description": "Collects a parallel workset objective, exclusive write paths, runtime configuration, validation gates, and evidence policy, then runs independent workers concurrently and returns every patch through one sequential integration lane.",
        "tagline": "Parallel owned-path delivery",
        "slug": PARALLEL_PIPELINE_TEMPLATE_ID,
        "worker_type": "parallel_workset_worker",
        "execution_model": "parallel",
        "worker_stage_label": "2. Parallel Work Config",
        "factory_stage_label": "4. Parallel Workset Execution",
        "validation_tier": "workset-contract",
        "risk": "high",
        "budget_spent_usd": 0.0,
        "budget_cap_usd": 20.0,
        "blueprint_version": "parallel-workset.v1",
        "tasks_completed": 0,
        "tasks_total": 7,
        "selected_worker": "workset-config",
        "max_parallel": 10,
        "input_manifest": "inputs/parallel-pipeline_input_manifest.json",
        "pipeline_config": "inputs/parallel-pipeline_pipeline_config.json",
        "execution_manifest": "execution/parallel_execution_manifest.json",
        "workers": [
            {
                "id": "workset-config",
                "title": "Workset Config Contract",
                "file": "parallel_workset_config.json",
                "description": "Normalize the objective, runtime limits, read context, and exclusive write-path contract before dispatch.",
                "stage": "repo",
                "manifest": "workers/parallel-pipeline_workset-config.json",
                "integration_config": "integration/configs/parallel-workset-config.json",
                "integration_receipt": "integration_receipts/parallel-pipeline_workset-config.json",
            },
            {
                "id": "parallel-split",
                "title": "Parallel Worker Split",
                "file": "parallel_worker_split.json",
                "description": "Split independent owned-path workstreams into runnable workset tasks with explicit dependencies.",
                "stage": "blueprint",
                "dependencies": ["workset-config"],
                "manifest": "workers/parallel-pipeline_parallel-split.json",
                "integration_config": "integration/configs/parallel-split.json",
                "integration_receipt": "integration_receipts/parallel-pipeline_parallel-split.json",
            },
            {
                "id": "serialized-integrator",
                "title": "Serialized Integrator",
                "file": "parallel_integrator.json",
                "description": "Accept worker receipts one at a time, apply only non-overlapping patches, and preserve rollback evidence.",
                "stage": "blueprint",
                "dependencies": ["parallel-split"],
                "manifest": "workers/parallel-pipeline_serialized-integrator.json",
                "integration_config": "integration/configs/serialized-integrator.json",
                "integration_receipt": "integration_receipts/parallel-pipeline_serialized-integrator.json",
            },
        ],
        "factory_steps": [
            {"id": "resolve-parallel-inputs", "title": "resolve_parallel_inputs", "file": "execution_run.json", "status": "accepted", "mode": "deterministic"},
            {"id": "write-parallel-workset", "title": "write_parallel_workset", "file": "workset.json", "status": "accepted", "mode": "deterministic", "dependencies": ["resolve-parallel-inputs"]},
            {"id": "dispatch-parallel-workers", "title": "dispatch_parallel_workers", "file": "workset_receipt.json", "status": "accepted", "mode": "api-openai-parallel", "dependencies": ["write-parallel-workset"]},
            {"id": "collect-worker-artifacts", "title": "collect_worker_artifacts", "file": "patch_bundles", "status": "accepted", "mode": "deterministic", "dependencies": ["dispatch-parallel-workers"]},
            {"id": "integrate-sequentially", "title": "integrate_sequentially", "file": "integration_receipts", "status": "accepted", "mode": "sequential", "dependencies": ["collect-worker-artifacts"]},
            {"id": "run-parallel-validation", "title": "run_parallel_validation", "file": "validation_receipts", "status": "accepted", "mode": "smoke", "dependencies": ["integrate-sequentially"]},
            {"id": "collect-parallel-evidence", "title": "collect_parallel_evidence", "file": "parallel_evidence.json", "status": "accepted", "mode": "deterministic", "dependencies": ["run-parallel-validation"]},
        ],
        "validators": [
            {"id": "exclusive-paths", "title": "Exclusive Path Validator", "file": "exclusive_paths_receipt.json", "receipt": "validation/exclusive_paths_receipt.json", "config": "validation/validator_configs/exclusive-paths.json", "mode": "schema", "blocking": True, "status": "passed"},
            {"id": "workset-receipt", "title": "Workset Receipt Validator", "file": "workset_receipt_validator.json", "receipt": "validation/workset_receipt_validator.json", "config": "validation/validator_configs/workset-receipt.json", "mode": "evidence", "blocking": True, "status": "passed"},
            {"id": "serialized-integration", "title": "Serialized Integration Validator", "file": "serialized_integration_receipt.json", "receipt": "validation/serialized_integration_receipt.json", "config": "validation/validator_configs/serialized-integration.json", "mode": "commands", "blocking": True, "status": "passed"},
        ],
        "evidence_artifacts": [
            {"id": "parallel-workset-manifest", "title": "Parallel Workset Manifest", "file": "workset.json", "status": "Configured", "kind": "artifact", "path": "execution/worksets/latest.json", "required_sources": ["parallel_worker_split.json"], "publish_policy": "Attach the runnable workset to every parallel pipeline handoff.", "retention_policy": "Keep with run artifacts."},
            {"id": "parallel-workset-receipt", "title": "Parallel Workset Receipt", "file": "workset_receipt.json", "status": "Configured", "kind": "receipt", "path": ".cento/worksets/*/workset_receipt.json", "required_sources": ["execution/worksets/*.json"], "publish_policy": "Use as proof that parallel workers converged through the serialized integration lane.", "retention_policy": "Keep with the workset run directory and pipeline evidence."},
            {"id": "parallel-handoff", "title": "Parallel Evidence Handoff", "file": "parallel_evidence.json", "status": "Configured", "kind": "bundle", "path": "evidence/parallel_evidence.json", "required_sources": ["workset_receipt.json", "validation_receipt.json"], "publish_policy": "Summarize changed paths, costs, worker outcomes, validators, and residual risks before review.", "retention_policy": "Keep with pipeline evidence."},
        ],
    }


def dev_pipeline_patch_swarm_project_defaults() -> dict[str, Any]:
    return {
        "id": PATCH_SWARM_PROJECT_ID,
        "label": "Patch Swarm Project",
        "surface": "Cento patch swarm candidate market",
        "surface_value": PATCH_SWARM_TEMPLATE_ID,
        "owned_root": "workspace/runs/parallel-delivery/patch-swarm",
        "read_paths": [
            "AGENTS.md",
            "README.md",
            "scripts/**",
            "templates/agent-work-app/**",
            "docs/**",
            "tests/**",
            "data/tools.json",
            ".cento/runtimes.yaml",
            ".cento/api_workers.yaml",
        ],
    }


def dev_pipeline_patch_swarm_blueprint_defaults() -> dict[str, Any]:
    proreq_steps = [
        ("request-decomposer", "request_decomposer", "request_decomposer.json"),
        ("codex-exec-adapter", "codex_exec_adapter", "codex_exec_adapter.json"),
        ("claude-code-adapter", "claude_code_adapter", "claude_code_adapter.json"),
        ("openai-patch-proposal-adapter", "openai_patch_proposal_adapter", "openai_patch_proposal_adapter.json"),
        ("candidate-normalizer", "candidate_normalizer", "candidate_normalizer.json"),
        ("dedupe-clustering", "dedupe_clustering", "dedupe_clustering.json"),
        ("deterministic-validator-fanout", "deterministic_validator_fanout", "deterministic_validator_fanout.json"),
        ("cost-latency-ledger", "cost_latency_ledger", "cost_latency_ledger.json"),
        ("dev-pipeline-studio-ui", "dev_pipeline_studio_ui", "dev_pipeline_studio_ui.json"),
        ("autopilot-coordinator-hooks", "autopilot_coordinator_hooks", "autopilot_coordinator_hooks.json"),
    ]
    return {
        "id": PATCH_SWARM_TEMPLATE_ID,
        "label": "Patch Swarm",
        "detail": "100+ candidate patches, 5+ agents, one serialized integrator",
        "description": "Runs ten ProReq execution lanes that can target Codex Exec, Claude Code, or OpenAI structured patch proposal workers, then feeds every candidate into one deterministic ranking and Safe Integrator handoff lane.",
        "tagline": "Massively parallel patch candidate market",
        "slug": PATCH_SWARM_TEMPLATE_ID,
        "worker_type": "patch_swarm_candidate_worker",
        "execution_model": "parallel",
        "worker_stage_label": "2. ProReq Patch Lanes",
        "factory_stage_label": "4. Candidate Swarm Execution",
        "validation_tier": "patch-swarm-contract",
        "risk": "high",
        "budget_spent_usd": 0.0,
        "budget_cap_usd": 20.0,
        "blueprint_version": "patch-swarm.v1",
        "tasks_completed": 0,
        "tasks_total": 11,
        "selected_worker": "request-decomposer",
        "max_parallel": 5,
        "input_manifest": "inputs/patch-swarm_input_manifest.json",
        "pipeline_config": "inputs/patch-swarm_pipeline_config.json",
        "execution_manifest": "execution/patch_swarm_execution_manifest.json",
        "workers": [
            {
                "id": step_id,
                "title": title.replace("_", " ").title(),
                "file": filename,
                "description": "One of ten ProReq pipeline executions that produces provider-compatible candidate patch receipts.",
                "stage": "blueprint",
                "manifest": f"workers/patch-swarm_{step_id}.json",
                "integration_config": f"integration/configs/patch-swarm-{step_id}.json",
                "integration_receipt": f"integration_receipts/patch-swarm_{step_id}.json",
            }
            for step_id, title, filename in proreq_steps
        ],
        "factory_steps": [
            {"id": step_id, "title": title, "file": filename, "status": "queued", "mode": "proreq-patch-lane"}
            for step_id, title, filename in proreq_steps
        ]
        + [
            {
                "id": "dedicated-integrator",
                "title": "dedicated_integrator",
                "file": "integration_execution.json",
                "status": "queued",
                "mode": "serialized-safe-integrator-handoff",
                "dependencies": [step_id for step_id, _title, _filename in proreq_steps],
            }
        ],
        "validators": [
            {"id": "candidate-count", "title": "100+ Candidate Validator", "file": "candidate_count_receipt.json", "receipt": "validation/patch_swarm_candidate_count.json", "config": "validation/validator_configs/patch-swarm-candidate-count.json", "mode": "schema", "blocking": True, "status": "passed"},
            {"id": "provider-mix", "title": "Provider Mix Validator", "file": "provider_mix_receipt.json", "receipt": "validation/patch_swarm_provider_mix.json", "config": "validation/validator_configs/patch-swarm-provider-mix.json", "mode": "schema", "blocking": True, "status": "passed"},
            {"id": "dedicated-integrator", "title": "Dedicated Integrator Validator", "file": "dedicated_integrator_receipt.json", "receipt": "validation/patch_swarm_integrator.json", "config": "validation/validator_configs/patch-swarm-integrator.json", "mode": "evidence", "blocking": True, "status": "passed"},
        ],
        "evidence_artifacts": [
            {"id": "patch-swarm-manifest", "title": "Patch Swarm Manifest", "file": "patch_swarm_manifest.json", "status": "Configured", "kind": "artifact", "path": "execution/patch-swarm/latest/patch_swarm_manifest.json", "required_sources": ["inputs/patch-swarm_input_manifest.json"], "publish_policy": "Attach the run manifest before candidate dispatch.", "retention_policy": "Keep with patch swarm run artifacts."},
            {"id": "candidate-index", "title": "Candidate Index", "file": "candidate_index.json", "status": "Configured", "kind": "artifact", "path": "execution/patch-swarm/latest/candidate_index.json", "required_sources": ["patch_swarm_manifest.json"], "publish_policy": "Use as the source of truth for candidate receipts, providers, costs, and validation state.", "retention_policy": "Keep with patch swarm run artifacts."},
            {"id": "safe-integrator-handoff", "title": "Safe Integrator Handoff", "file": "safe_integrator_handoff.json", "status": "Configured", "kind": "bundle", "path": "execution/patch-swarm/latest/safe_integrator_handoff.json", "required_sources": ["candidate_index.json", "ranking.json", "integration_execution.json"], "publish_policy": "Publish only after the dedicated integrator selects winners.", "retention_policy": "Keep with patch swarm run artifacts."},
        ],
    }


def dev_pipeline_hard_proreq_project_defaults() -> dict[str, Any]:
    return {
        "id": HARD_PROREQ_PROJECT_ID,
        "label": "Hard Proreq Project",
        "surface": "Cento pro requirements route",
        "surface_value": HARD_PROREQ_TEMPLATE_ID,
        "owned_root": "workspace/runs/hard-proreq/outputs",
        "read_paths": [
            "AGENTS.md",
            "README.md",
            "scripts/**",
            "templates/agent-work-app/**",
            "docs/**",
            "tests/**",
            "data/tools.json",
            ".cento/api_workers.yaml",
        ],
    }


def dev_pipeline_hard_proreq_schema() -> dict[str, Any]:
    text = {"type": "string"}
    text_array = {"type": "array", "items": {"type": "string"}}
    workstream = {
        "type": "object",
        "properties": {
            "id": text,
            "title": text,
            "intent": text,
            "owned_paths": text_array,
            "read_paths": text_array,
            "depends_on": text_array,
            "validation_commands": text_array,
            "handoff_artifacts": text_array,
        },
        "required": ["id", "title", "intent", "owned_paths", "read_paths", "depends_on", "validation_commands", "handoff_artifacts"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "schema_version": {"type": "string", "enum": ["cento.hard_proreq_backend_plan.v1"]},
            "summary": text,
            "backend_workstreams": {"type": "array", "items": workstream},
            "integration_plan": text_array,
            "validation_plan": text_array,
            "parallelization_notes": text_array,
            "codex_exec_prompts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": text,
                        "prompt": text,
                        "output_schema": text,
                    },
                    "required": ["id", "prompt", "output_schema"],
                    "additionalProperties": False,
                },
            },
            "risks": text_array,
        },
        "required": [
            "schema_version",
            "summary",
            "backend_workstreams",
            "integration_plan",
            "validation_plan",
            "parallelization_notes",
            "codex_exec_prompts",
            "risks",
        ],
        "additionalProperties": False,
    }


def dev_pipeline_hard_proreq_blueprint_defaults() -> dict[str, Any]:
    return {
        "id": HARD_PROREQ_TEMPLATE_ID,
        "label": "Hard proreq task",
        "detail": "Manifest-backed requirement planning with optional screenshot context",
        "description": "Transforms operator thoughts, optional screenshot context, and questionnaire answers into Cento context, ten story manifests, parallel patch workset handoff, manifest-driven integration, validation, and evidence.",
        "tagline": "Default hard prompt route",
        "slug": HARD_PROREQ_TEMPLATE_ID,
        "worker_type": "hard_proreq_worker",
        "execution_model": "ordered",
        "worker_stage_label": "2. Cento Context",
        "factory_stage_label": "4. Proreq Planning",
        "validation_tier": "proreq-contract",
        "risk": "high",
        "budget_spent_usd": 0.0,
        "budget_cap_usd": 20.0,
        "blueprint_version": "hard-proreq.v1",
        "tasks_completed": 0,
        "tasks_total": 10,
        "selected_worker": "mini-cento-context",
        "input_manifest": "inputs/hard-proreq-task_input_manifest.json",
        "pipeline_config": "inputs/hard-proreq-task_pipeline_config.json",
        "execution_manifest": "execution/execution_manifest.json",
        "workers": [
            {
                "id": "mini-cento-context",
                "title": "Mini Cento Context",
                "file": "mini_cento_context.json",
                "description": "Use Cento-native context gathering and repo search to summarize the task surface before pro planning.",
                "stage": "repo",
                "manifest": "workers/hard-proreq-task_mini-cento-context.json",
                "integration_config": "integration/configs/mini-cento-context.json",
                "integration_receipt": "integration_receipts/hard-proreq-task_mini-cento-context.json",
            },
            {
                "id": "proreq-splitter",
                "title": "Prompt Splitter",
                "file": "proreq_prompt_split.json",
                "description": "Split operator input into optional muted UI screenshot context, ten story manifests, and a schema-backed backend planning request.",
                "stage": "blueprint",
                "dependencies": ["mini-cento-context"],
                "manifest": "workers/hard-proreq-task_proreq-splitter.json",
                "integration_config": "integration/configs/proreq-splitter.json",
                "integration_receipt": "integration_receipts/hard-proreq-task_proreq-splitter.json",
            },
            {
                "id": "backend-work-materializer",
                "title": "Backend Work Materializer",
                "file": "backend_work_manifest.json",
                "description": "Turn GPT pro backend plan output into Cento-native backend work prompts and validation gates.",
                "stage": "blueprint",
                "dependencies": ["proreq-splitter"],
                "manifest": "workers/hard-proreq-task_backend-work-materializer.json",
                "integration_config": "integration/configs/backend-work-materializer.json",
                "integration_receipt": "integration_receipts/hard-proreq-task_backend-work-materializer.json",
            },
        ],
        "factory_steps": [
            {"id": "collect-operator-intake", "title": "collect_operator_intake", "file": "operator_intake.json", "status": "accepted", "mode": "deterministic"},
            {"id": "build-cento-context", "title": "build_mini_cento_context", "file": "mini_cento_context.json", "status": "accepted", "mode": "deterministic", "dependencies": ["collect-operator-intake"]},
            {"id": "write-ui-screenshot-request", "title": "ui_screenshot_request_muted", "file": "ui_screenshot_request.json", "status": "muted", "mode": "frontend-separate", "muted": True, "lane": "frontend", "dependencies": ["build-cento-context"]},
            {"id": "prepare-pro-backend-request", "title": "prepare_gpt_pro_backend_request", "file": "pro_backend_request.json", "status": "accepted", "mode": "structured-output", "dependencies": ["build-cento-context"]},
            {"id": "dispatch-pro-backend-plan", "title": "gpt_pro_backend_plan", "file": "pro_backend_plan.json", "status": "accepted", "mode": "api-openai-pro", "dependencies": ["prepare-pro-backend-request"]},
            {"id": "materialize-backend-work", "title": "materialize_10_story_backend_work", "file": "backend_work_manifest.json", "status": "accepted", "mode": "cento-native", "dependencies": ["dispatch-pro-backend-plan"]},
            {"id": "write-integration-plan", "title": "write_integration_plan", "file": "integration_plan.json", "status": "accepted", "mode": "deterministic", "dependencies": ["materialize-backend-work"]},
            {"id": "write-validation-plan", "title": "write_validation_plan", "file": "validation_plan.json", "status": "accepted", "mode": "deterministic", "dependencies": ["write-integration-plan"]},
            {"id": "collect-proreq-evidence", "title": "collect_proreq_evidence", "file": "hard_proreq_evidence.json", "status": "accepted", "mode": "deterministic", "dependencies": ["write-validation-plan"]},
        ],
        "validators": [
            {"id": "schema", "title": "Schema Validator", "file": "schema_receipt.json", "receipt": "validation/schema_receipt.json", "config": "validation/validator_configs/schema.json", "mode": "schema", "blocking": True, "status": "passed"},
            {"id": "proreq-contract", "title": "Proreq Contract Validator", "file": "proreq_contract_receipt.json", "receipt": "validation/proreq_contract_receipt.json", "config": "validation/validator_configs/proreq-contract.json", "mode": "schema", "blocking": True, "status": "passed"},
            {"id": "frontend-muted", "title": "Muted Frontend Flow Validator", "file": "frontend_muted_receipt.json", "receipt": "validation/frontend_muted_receipt.json", "config": "validation/validator_configs/frontend-muted.json", "mode": "evidence", "blocking": False, "status": "muted"},
        ],
        "evidence_artifacts": [
            {"id": "pro-backend-request", "title": "GPT Pro Backend Request", "file": "pro_backend_request.json", "status": "Configured", "kind": "artifact", "path": "execution/hard-proreq/latest/pro_backend_request.json", "required_sources": ["operator_intake.json", "mini_cento_context.json", "pro_output_schema.json"], "publish_policy": "Attach the schema-backed request to every hard proreq handoff.", "retention_policy": "Keep with run artifacts."},
            {"id": "backend-work-manifest", "title": "Cento Backend Work Manifest", "file": "backend_work_manifest.json", "status": "Configured", "kind": "artifact", "path": "execution/hard-proreq/latest/backend_work_manifest.json", "required_sources": ["pro_backend_plan.json"], "publish_policy": "Use as the Codex/Cento backend work launcher input for ten story manifests and the parallel patch workset.", "retention_policy": "Keep with run artifacts."},
        ],
    }


def dev_pipeline_proreq_light_project_defaults() -> dict[str, Any]:
    project = deepcopy(dev_pipeline_hard_proreq_project_defaults())
    project.update(
        {
            "id": PROREQ_LIGHT_PROJECT_ID,
            "label": "ProReq Light Project",
            "surface": "Cento Codex Exec requirements route",
            "surface_value": PROREQ_LIGHT_TEMPLATE_ID,
            "owned_root": "workspace/runs/proreq-light/outputs",
        }
    )
    return project


def dev_pipeline_proreq_light_blueprint_defaults() -> dict[str, Any]:
    template = deepcopy(dev_pipeline_hard_proreq_blueprint_defaults())
    template.update(
        {
            "id": PROREQ_LIGHT_TEMPLATE_ID,
            "label": "ProReq light task",
            "detail": "Codex Exec requirement planning with optional screenshot context",
            "description": "Transforms operator thoughts, optional screenshot context, and Cento context into the same ten-story ProReq artifacts, but replaces the live ChatGPT Pro API call with a Codex Exec prompt that simulates the Pro planning lane.",
            "tagline": "Codex Exec ProReq route",
            "slug": PROREQ_LIGHT_TEMPLATE_ID,
            "worker_type": "proreq_light_codex_worker",
            "factory_stage_label": "4. ProReq Light Planning",
            "validation_tier": "proreq-light-contract",
            "risk": "medium",
            "budget_spent_usd": 0.0,
            "budget_cap_usd": 0.0,
            "blueprint_version": "proreq-light.v1",
            "selected_worker": "mini-cento-context",
        }
    )
    for worker in template.get("workers", []):
        if not isinstance(worker, dict):
            continue
        if worker.get("id") == "proreq-splitter":
            worker["title"] = "Codex Pro Prompt Splitter"
            worker["description"] = "Prepare the strict schema and Codex Exec prompt that starts with \"You're chatGPT Pro model\" instead of dispatching a live Pro API call."
        elif worker.get("id") == "backend-work-materializer":
            worker["description"] = "Turn the Codex Exec ProReq-light plan into Cento-native story manifests and validation gates."
    for step in template.get("factory_steps", []):
        if not isinstance(step, dict):
            continue
        if step.get("id") == "prepare-pro-backend-request":
            step["title"] = "prepare_codex_pro_backend_request"
            step["mode"] = "codex-exec-request"
        elif step.get("id") == "dispatch-pro-backend-plan":
            step["id"] = "dispatch-codex-pro-backend-plan"
            step["title"] = "codex_exec_pro_backend_plan"
            step["mode"] = "codex-exec-proreq-light"
    for artifact in template.get("evidence_artifacts", []):
        if not isinstance(artifact, dict):
            continue
        if artifact.get("id") == "pro-backend-request":
            artifact["title"] = "Codex Exec ProReq Prompt"
            artifact["file"] = "proreq_light_codex_prompt.md"
            artifact["path"] = "execution/hard-proreq/latest/proreq_light_codex_prompt.md"
            artifact["required_sources"] = ["operator_intake.json", "mini_cento_context.json", "pro_output_schema.json", "pro_backend_request.json"]
            artifact["publish_policy"] = "Attach the Codex Exec prompt and command receipt to every ProReq-light handoff."
        elif artifact.get("id") == "backend-work-manifest":
            artifact["required_sources"] = ["pro_backend_plan.json", "proreq_light_codex_response.json"]
    template.setdefault("evidence_artifacts", []).append(
        {
            "id": "codex-proreq-light-response",
            "title": "Codex Exec ProReq Response",
            "file": "proreq_light_codex_response.json",
            "status": "Configured",
            "kind": "artifact",
            "path": "execution/hard-proreq/latest/proreq_light_codex_response.json",
            "required_sources": ["proreq_light_codex_prompt.md", "proreq_light_output_schema.json", "proreq_light_codex_command.json"],
            "publish_policy": "Preserve Codex Exec stdout/stderr and fallback status for every light run.",
            "retention_policy": "Keep with run artifacts.",
        }
    )
    return template


def dev_pipeline_multipipeline_project_defaults() -> dict[str, Any]:
    return {
        "id": MULTIPIPELINE_PROJECT_ID,
        "label": "Multipipeline ProReq Project",
        "surface": "Sequential ProReq meta-pipeline",
        "surface_value": MULTIPIPELINE_TEMPLATE_ID,
        "owned_root": "workspace/runs/multipipeline-proreq/outputs",
        "read_paths": [
            "AGENTS.md",
            "README.md",
            "scripts/**",
            "templates/agent-work-app/**",
            "docs/**",
            "tests/**",
            "data/tools.json",
            ".cento/api_workers.yaml",
        ],
    }


def dev_pipeline_multipipeline_blueprint_defaults() -> dict[str, Any]:
    return {
        "id": MULTIPIPELINE_TEMPLATE_ID,
        "label": "Multipipeline ProReq chain",
        "detail": "Four sequential ProReq passes where each pass feeds guidance to the next",
        "description": "Schedules four ordered ProReq request passes for an operator-defined multipipeline objective. Each pass consumes the previous pass guidance, writes the next ProReq request, preserves UI screenshot guidance, prepares a ChatGPT Pro request, and emits validation-ready evidence.",
        "tagline": "Sequential ProReq coordinator",
        "slug": MULTIPIPELINE_TEMPLATE_ID,
        "worker_type": "multipipeline_proreq_coordinator",
        "execution_model": "ordered",
        "worker_stage_label": "2. Multipipeline Context",
        "factory_stage_label": "4. Sequential ProReq Passes",
        "validation_tier": "multipipeline-contract",
        "risk": "medium",
        "budget_spent_usd": 0.0,
        "budget_cap_usd": 0.0,
        "blueprint_version": "multipipeline-proreq-chain.v1",
        "tasks_completed": 0,
        "tasks_total": 9,
        "selected_worker": "chain-scheduler",
        "input_manifest": "inputs/multipipeline-proreq-chain_input_manifest.json",
        "pipeline_config": "inputs/multipipeline-proreq-chain_pipeline_config.json",
        "execution_manifest": "execution/multipipeline_execution_manifest.json",
        "workers": [
            {
                "id": "chain-intake",
                "title": "Meta-pipeline Intake",
                "file": "operator_intake.json",
                "description": "Normalize the operator objective, improvement boundaries, and compute policy before scheduling child ProReq passes.",
                "stage": "repo",
                "manifest": "workers/multipipeline-proreq-chain_chain-intake.json",
                "integration_config": "integration/configs/multipipeline-chain-intake.json",
                "integration_receipt": "integration_receipts/multipipeline-proreq-chain_chain-intake.json",
            },
            {
                "id": "chain-scheduler",
                "title": "Sequential ProReq Scheduler",
                "file": "multipipeline_schedule.json",
                "description": "Create four ordered ProReq pass requests, each dependent on the previous pass guidance artifact.",
                "stage": "blueprint",
                "dependencies": ["chain-intake"],
                "manifest": "workers/multipipeline-proreq-chain_chain-scheduler.json",
                "integration_config": "integration/configs/multipipeline-chain-scheduler.json",
                "integration_receipt": "integration_receipts/multipipeline-proreq-chain_chain-scheduler.json",
            },
            {
                "id": "chain-handoff",
                "title": "Guidance And Evidence Handoff",
                "file": "multipipeline_evidence.json",
                "description": "Collect pass receipts, UI screenshot prompt, ChatGPT Pro request, roadmap, and validation handoff evidence.",
                "stage": "blueprint",
                "dependencies": ["chain-scheduler"],
                "manifest": "workers/multipipeline-proreq-chain_chain-handoff.json",
                "integration_config": "integration/configs/multipipeline-chain-handoff.json",
                "integration_receipt": "integration_receipts/multipipeline-proreq-chain_chain-handoff.json",
            },
        ],
        "factory_steps": [
            {"id": "collect-multipipeline-intake", "title": "collect_multipipeline_intake", "file": "operator_intake.json", "status": "accepted", "mode": "deterministic"},
            {"id": "write-multipipeline-schedule", "title": "write_multipipeline_schedule", "file": "multipipeline_schedule.json", "status": "accepted", "mode": "deterministic", "dependencies": ["collect-multipipeline-intake"]},
            {"id": "run-proreq-pass-1", "title": "proreq_pass_1_scope", "file": "pass_01_proreq_request.json", "status": "accepted", "mode": "request-artifact", "dependencies": ["write-multipipeline-schedule"]},
            {"id": "run-proreq-pass-2", "title": "proreq_pass_2_architecture", "file": "pass_02_proreq_request.json", "status": "accepted", "mode": "request-artifact", "dependencies": ["run-proreq-pass-1"]},
            {"id": "run-proreq-pass-3", "title": "proreq_pass_3_integration", "file": "pass_03_proreq_request.json", "status": "accepted", "mode": "request-artifact", "dependencies": ["run-proreq-pass-2"]},
            {"id": "run-proreq-pass-4", "title": "proreq_pass_4_validation", "file": "pass_04_proreq_request.json", "status": "accepted", "mode": "request-artifact", "dependencies": ["run-proreq-pass-3"]},
            {"id": "write-multipipeline-ui-screenshot-request", "title": "write_ui_screenshot_request", "file": "ui_screenshot_request.json", "status": "muted", "mode": "frontend-separate", "muted": True, "lane": "frontend", "dependencies": ["run-proreq-pass-4"]},
            {"id": "write-multipipeline-pro-request", "title": "write_chatgpt_pro_request", "file": "chatgpt_pro_request.json", "status": "accepted", "mode": "structured-output", "dependencies": ["write-multipipeline-ui-screenshot-request"]},
            {"id": "collect-multipipeline-evidence", "title": "collect_multipipeline_evidence", "file": "multipipeline_evidence.json", "status": "accepted", "mode": "deterministic", "dependencies": ["write-multipipeline-pro-request"]},
        ],
        "validators": [
            {"id": "sequential-schedule", "title": "Sequential Schedule Validator", "file": "sequential_schedule_receipt.json", "receipt": "validation/sequential_schedule_receipt.json", "config": "validation/validator_configs/sequential-schedule.json", "mode": "schema", "blocking": True, "status": "passed"},
            {"id": "proreq-pass-handoff", "title": "ProReq Pass Handoff Validator", "file": "proreq_pass_handoff_receipt.json", "receipt": "validation/proreq_pass_handoff_receipt.json", "config": "validation/validator_configs/proreq-pass-handoff.json", "mode": "evidence", "blocking": True, "status": "passed"},
            {"id": "ui-pro-request", "title": "UI And Pro Request Validator", "file": "ui_pro_request_receipt.json", "receipt": "validation/ui_pro_request_receipt.json", "config": "validation/validator_configs/ui-pro-request.json", "mode": "evidence", "blocking": False, "status": "passed"},
        ],
        "evidence_artifacts": [
            {"id": "multipipeline-schedule", "title": "Multipipeline Schedule", "file": "multipipeline_schedule.json", "status": "Configured", "kind": "artifact", "path": "execution/multipipeline/latest/multipipeline_schedule.json", "required_sources": ["operator_intake.json"], "publish_policy": "Attach to every meta-pipeline handoff before sequential ProReq pass execution.", "retention_policy": "Keep with run artifacts."},
            {"id": "multipipeline-pass-guidance", "title": "Sequential Pass Guidance", "file": "pass_04_guidance.json", "status": "Configured", "kind": "artifact", "path": "execution/multipipeline/latest/pass_04_guidance.json", "required_sources": ["pass_01_guidance.json", "pass_02_guidance.json", "pass_03_guidance.json"], "publish_policy": "Use the final pass guidance as the next operator prompt or implementation request.", "retention_policy": "Keep with run artifacts."},
            {"id": "multipipeline-evidence", "title": "Meta-pipeline Evidence", "file": "multipipeline_evidence.json", "status": "Configured", "kind": "bundle", "path": "execution/multipipeline/latest/multipipeline_evidence.json", "required_sources": ["multipipeline_schedule.json", "ui_screenshot_request.json", "chatgpt_pro_request.json"], "publish_policy": "Publish after all four pass request artifacts and validation handoff are present.", "retention_policy": "Keep with run artifacts."},
        ],
    }


def dev_pipeline_merge_default_fields(current: dict[str, Any], default: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(current)
    for key, value in default.items():
        if key not in merged or merged.get(key) is None:
            merged[key] = deepcopy(value)
    return merged


def dev_pipeline_migrate_run_pipeline_wording(item: dict[str, Any]) -> dict[str, Any]:
    for key in ("title", "detail", "evidence_policy", "answer_notes"):
        if isinstance(item.get(key), str):
            item[key] = str(item[key]).replace("New Issue", "Run Pipeline").replace("New issue", "Run pipeline")
    return item


def dev_pipeline_merge_builtin_item(current: dict[str, Any], default: dict[str, Any], forced_keys: tuple[str, ...]) -> dict[str, Any]:
    merged = dev_pipeline_merge_default_fields(current, default)
    for key in forced_keys:
        if key in default:
            merged[key] = deepcopy(default[key])
    return merged


def dev_pipeline_ensure_builtin_pipelines(manifest: dict[str, Any]) -> bool:
    changed = False
    projects = manifest.get("projects")
    if not isinstance(projects, list):
        projects = []
        manifest["projects"] = projects
        changed = True
    project_defaults = [
        dev_pipeline_hard_proreq_project_defaults(),
        dev_pipeline_proreq_light_project_defaults(),
        dev_pipeline_multipipeline_project_defaults(),
        dev_pipeline_parallel_project_defaults(),
        dev_pipeline_patch_swarm_project_defaults(),
    ]
    for index, default_project in enumerate(project_defaults):
        project_id = str(default_project.get("id") or "")
        if not any(isinstance(item, dict) and str(item.get("id") or "") == project_id for item in projects):
            projects.insert(min(index, len(projects)), default_project)
            changed = True

    templates = manifest.get("templates")
    if not isinstance(templates, list):
        templates = []
        manifest["templates"] = templates
        changed = True
    template_defaults = [
        dev_pipeline_hard_proreq_blueprint_defaults(),
        dev_pipeline_proreq_light_blueprint_defaults(),
        dev_pipeline_multipipeline_blueprint_defaults(),
        dev_pipeline_parallel_blueprint_defaults(),
        dev_pipeline_patch_swarm_blueprint_defaults(),
    ]
    for index, default_template in enumerate(template_defaults):
        template_id = str(default_template.get("id") or "")
        if not any(isinstance(item, dict) and str(item.get("id") or "") == template_id for item in templates):
            templates.insert(min(index, len(templates)), default_template)
            changed = True

    defaults = manifest.get("defaults") if isinstance(manifest.get("defaults"), dict) else {}
    project_ids = {str(item.get("id") or "") for item in projects if isinstance(item, dict)}
    template_ids = {str(item.get("id") or "") for item in templates if isinstance(item, dict)}
    if str(defaults.get("project_id") or "") not in project_ids:
        defaults["project_id"] = DEFAULT_DEV_PIPELINE_PROJECT_ID
        changed = True
    if str(defaults.get("template_id") or "") not in template_ids:
        defaults["template_id"] = DEFAULT_DEV_PIPELINE_TEMPLATE_ID
        changed = True
    if changed:
        manifest["defaults"] = defaults
    return changed


def dev_pipeline_apply_generic_blueprint(template: dict[str, Any]) -> dict[str, Any]:
    if str(template.get("id") or "") in {HARD_PROREQ_TEMPLATE_ID, PROREQ_LIGHT_TEMPLATE_ID}:
        defaults = dev_pipeline_proreq_light_blueprint_defaults() if str(template.get("id") or "") == PROREQ_LIGHT_TEMPLATE_ID else dev_pipeline_hard_proreq_blueprint_defaults()
        for key in ("label", "detail", "description", "tagline", "worker_type", "execution_model", "worker_stage_label", "factory_stage_label", "blueprint_version", "tasks_completed", "tasks_total", "validation_tier", "risk", "budget_cap_usd", "input_manifest", "pipeline_config", "execution_manifest"):
            if key not in template or template.get(key) is None or (isinstance(template.get(key), str) and not str(template.get(key)).strip()):
                template[key] = deepcopy(defaults[key])
        for key in ("detail", "description", "factory_stage_label", "tasks_total", "budget_cap_usd", "blueprint_version"):
            template[key] = deepcopy(defaults[key])
        for list_key in ("workers", "factory_steps", "validators", "evidence_artifacts"):
            default_items = {str(item.get("id") or ""): item for item in defaults.get(list_key, []) if isinstance(item, dict)}
            raw_items = template.get(list_key)
            forced_keys = {
                "workers": ("title", "file", "description", "stage", "dependencies", "manifest", "integration_config", "integration_receipt"),
                "factory_steps": ("title", "file", "mode", "muted", "lane", "dependencies"),
                "validators": ("title", "file", "receipt", "config", "mode", "blocking"),
                "evidence_artifacts": ("title", "file", "kind", "path", "required_sources", "publish_policy", "retention_policy"),
            }.get(list_key, ())
            if isinstance(raw_items, list):
                seen: set[str] = set()
                merged_items = []
                for item in raw_items:
                    if not isinstance(item, dict):
                        continue
                    item_id = str(item.get("id") or "")
                    seen.add(item_id)
                    merged_items.append(dev_pipeline_merge_builtin_item(item, default_items.get(item_id, {}), forced_keys))
                for item_id, default_item in default_items.items():
                    if item_id not in seen:
                        merged_items.append(deepcopy(default_item))
                template[list_key] = merged_items
            else:
                template[list_key] = deepcopy(defaults[list_key])
        default_inputs = dev_pipeline_default_required_inputs(str(template.get("id") or HARD_PROREQ_TEMPLATE_ID))
        default_input_map = {str(item.get("id") or ""): item for item in default_inputs if isinstance(item, dict)}
        raw_inputs = template.get("required_inputs")
        if isinstance(raw_inputs, list):
            seen_inputs: set[str] = set()
            merged_inputs = []
            forced_input_keys = (
                "title",
                "detail",
                "kind",
                "source",
                "automation",
                "format",
                "questions",
                "paths",
                "path_policy",
                "artifacts",
                "image_refs",
                "image_notes",
                "evidence_policy",
                "required",
                "muted",
                "blocking",
            )
            for item in raw_inputs:
                if not isinstance(item, dict):
                    continue
                item_id = str(item.get("id") or "")
                seen_inputs.add(item_id)
                merged_inputs.append(dev_pipeline_migrate_run_pipeline_wording(dev_pipeline_merge_builtin_item(item, default_input_map.get(item_id, {}), forced_input_keys)))
            for item_id, default_item in default_input_map.items():
                if item_id not in seen_inputs:
                    merged_inputs.append(dev_pipeline_migrate_run_pipeline_wording(deepcopy(default_item)))
            template["required_inputs"] = merged_inputs
        else:
            template["required_inputs"] = [dev_pipeline_migrate_run_pipeline_wording(item) for item in default_inputs]
        screenshot_defaults = default_input_map.get("ui-screenshot-request", {})
        for item in template.get("required_inputs", []):
            if not isinstance(item, dict) or str(item.get("id") or "") != "ui-screenshot-request":
                continue
            item["image_refs"] = list(
                dict.fromkeys(
                    dev_pipeline_text_list(item.get("image_refs"), [])
                    + dev_pipeline_text_list(screenshot_defaults.get("image_refs"), [])
                )
            )
            item["artifacts"] = list(
                dict.fromkeys(
                    dev_pipeline_text_list(item.get("artifacts"), [])
                    + dev_pipeline_text_list(screenshot_defaults.get("artifacts"), [])
                )
            )
        workers = [worker for worker in template.get("workers", []) if isinstance(worker, dict)]
        if not any(str(worker.get("id") or "") == str(template.get("selected_worker") or "") for worker in workers):
            template["selected_worker"] = str(workers[0].get("id") or "") if workers else ""
        return template

    if str(template.get("id") or "") == MULTIPIPELINE_TEMPLATE_ID:
        defaults = dev_pipeline_multipipeline_blueprint_defaults()
        for key in ("label", "detail", "description", "tagline", "worker_type", "execution_model", "worker_stage_label", "factory_stage_label", "blueprint_version", "tasks_completed", "tasks_total", "validation_tier", "risk", "budget_cap_usd", "input_manifest", "pipeline_config", "execution_manifest"):
            if key not in template or template.get(key) is None or (isinstance(template.get(key), str) and not str(template.get(key)).strip()):
                template[key] = deepcopy(defaults[key])
        for key in ("detail", "description", "factory_stage_label", "tasks_total", "budget_cap_usd", "blueprint_version"):
            template[key] = deepcopy(defaults[key])
        for list_key in ("workers", "factory_steps", "validators", "evidence_artifacts"):
            default_items = {str(item.get("id") or ""): item for item in defaults.get(list_key, []) if isinstance(item, dict)}
            raw_items = template.get(list_key)
            forced_keys = {
                "workers": ("title", "file", "description", "stage", "dependencies", "manifest", "integration_config", "integration_receipt"),
                "factory_steps": ("title", "file", "mode", "muted", "lane", "dependencies"),
                "validators": ("title", "file", "receipt", "config", "mode", "blocking"),
                "evidence_artifacts": ("title", "file", "kind", "path", "required_sources", "publish_policy", "retention_policy"),
            }.get(list_key, ())
            if isinstance(raw_items, list):
                seen: set[str] = set()
                merged_items = []
                for item in raw_items:
                    if not isinstance(item, dict):
                        continue
                    item_id = str(item.get("id") or "")
                    seen.add(item_id)
                    merged_items.append(dev_pipeline_merge_builtin_item(item, default_items.get(item_id, {}), forced_keys))
                for item_id, default_item in default_items.items():
                    if item_id not in seen:
                        merged_items.append(deepcopy(default_item))
                template[list_key] = merged_items
            else:
                template[list_key] = deepcopy(defaults[list_key])
        default_inputs = dev_pipeline_default_required_inputs(MULTIPIPELINE_TEMPLATE_ID)
        default_input_map = {str(item.get("id") or ""): item for item in default_inputs if isinstance(item, dict)}
        raw_inputs = template.get("required_inputs")
        if isinstance(raw_inputs, list):
            seen_inputs: set[str] = set()
            merged_inputs = []
            forced_input_keys = (
                "title",
                "detail",
                "kind",
                "source",
                "automation",
                "format",
                "questions",
                "paths",
                "path_policy",
                "artifacts",
                "image_refs",
                "image_notes",
                "evidence_policy",
                "required",
                "muted",
                "blocking",
                "answer",
            )
            for item in raw_inputs:
                if not isinstance(item, dict):
                    continue
                item_id = str(item.get("id") or "")
                seen_inputs.add(item_id)
                merged_inputs.append(dev_pipeline_migrate_run_pipeline_wording(dev_pipeline_merge_builtin_item(item, default_input_map.get(item_id, {}), forced_input_keys)))
            for item_id, default_item in default_input_map.items():
                if item_id not in seen_inputs:
                    merged_inputs.append(dev_pipeline_migrate_run_pipeline_wording(deepcopy(default_item)))
            template["required_inputs"] = merged_inputs
        else:
            template["required_inputs"] = [dev_pipeline_migrate_run_pipeline_wording(item) for item in default_inputs]
        workers = [worker for worker in template.get("workers", []) if isinstance(worker, dict)]
        if not any(str(worker.get("id") or "") == str(template.get("selected_worker") or "") for worker in workers):
            template["selected_worker"] = str(workers[0].get("id") or "") if workers else ""
        return template

    if str(template.get("id") or "") == PARALLEL_PIPELINE_TEMPLATE_ID:
        defaults = dev_pipeline_parallel_blueprint_defaults()
        for key in ("label", "detail", "description", "tagline", "worker_type", "execution_model", "worker_stage_label", "factory_stage_label", "blueprint_version", "tasks_completed", "tasks_total", "validation_tier", "risk", "budget_cap_usd", "input_manifest", "pipeline_config", "execution_manifest", "max_parallel"):
            if key not in template or template.get(key) is None or (isinstance(template.get(key), str) and not str(template.get(key)).strip()):
                template[key] = deepcopy(defaults[key])
        for key in ("detail", "description", "tasks_total", "budget_cap_usd", "max_parallel", "blueprint_version"):
            template[key] = deepcopy(defaults[key])
        for list_key in ("workers", "factory_steps", "validators", "evidence_artifacts"):
            default_items = {str(item.get("id") or ""): item for item in defaults.get(list_key, []) if isinstance(item, dict)}
            raw_items = template.get(list_key)
            if isinstance(raw_items, list):
                seen: set[str] = set()
                merged_items = []
                for item in raw_items:
                    if not isinstance(item, dict):
                        continue
                    item_id = str(item.get("id") or "")
                    seen.add(item_id)
                    merged_items.append(dev_pipeline_merge_default_fields(item, default_items.get(item_id, {})))
                for item_id, default_item in default_items.items():
                    if item_id not in seen:
                        merged_items.append(deepcopy(default_item))
                template[list_key] = merged_items
            else:
                template[list_key] = deepcopy(defaults[list_key])
        default_inputs = dev_pipeline_default_required_inputs(PARALLEL_PIPELINE_TEMPLATE_ID)
        default_input_map = {str(item.get("id") or ""): item for item in default_inputs if isinstance(item, dict)}
        raw_inputs = template.get("required_inputs")
        if isinstance(raw_inputs, list):
            seen_inputs: set[str] = set()
            merged_inputs = []
            forced_input_keys = (
                "title",
                "detail",
                "kind",
                "source",
                "automation",
                "format",
                "questions",
                "paths",
                "path_policy",
                "artifacts",
                "evidence_policy",
                "required",
                "advanced",
                "status",
                "answer",
            )
            for item in raw_inputs:
                if not isinstance(item, dict):
                    continue
                item_id = str(item.get("id") or "")
                seen_inputs.add(item_id)
                merged_inputs.append(dev_pipeline_merge_builtin_item(item, default_input_map.get(item_id, {}), forced_input_keys))
            for item_id, default_item in default_input_map.items():
                if item_id not in seen_inputs:
                    merged_inputs.append(deepcopy(default_item))
            template["required_inputs"] = merged_inputs
        else:
            template["required_inputs"] = default_inputs
        workers = [worker for worker in template.get("workers", []) if isinstance(worker, dict)]
        if not any(str(worker.get("id") or "") == str(template.get("selected_worker") or "") for worker in workers):
            template["selected_worker"] = str(workers[0].get("id") or "") if workers else ""
        return template

    if str(template.get("id") or "") == PATCH_SWARM_TEMPLATE_ID:
        defaults = dev_pipeline_patch_swarm_blueprint_defaults()
        for key in ("label", "detail", "description", "tagline", "worker_type", "execution_model", "worker_stage_label", "factory_stage_label", "blueprint_version", "tasks_completed", "tasks_total", "validation_tier", "risk", "budget_cap_usd", "input_manifest", "pipeline_config", "execution_manifest", "max_parallel"):
            if key not in template or template.get(key) is None or (isinstance(template.get(key), str) and not str(template.get(key)).strip()):
                template[key] = deepcopy(defaults[key])
        for key in ("detail", "description", "tasks_total", "budget_cap_usd", "max_parallel", "blueprint_version"):
            template[key] = deepcopy(defaults[key])
        for list_key in ("workers", "factory_steps", "validators", "evidence_artifacts"):
            default_items = {str(item.get("id") or ""): item for item in defaults.get(list_key, []) if isinstance(item, dict)}
            raw_items = template.get(list_key)
            if isinstance(raw_items, list):
                seen: set[str] = set()
                merged_items = []
                for item in raw_items:
                    if not isinstance(item, dict):
                        continue
                    item_id = str(item.get("id") or "")
                    seen.add(item_id)
                    merged_items.append(dev_pipeline_merge_default_fields(item, default_items.get(item_id, {})))
                for item_id, default_item in default_items.items():
                    if item_id not in seen:
                        merged_items.append(deepcopy(default_item))
                template[list_key] = merged_items
            else:
                template[list_key] = deepcopy(defaults[list_key])
        default_inputs = dev_pipeline_default_required_inputs(PATCH_SWARM_TEMPLATE_ID)
        default_input_map = {str(item.get("id") or ""): item for item in default_inputs if isinstance(item, dict)}
        raw_inputs = template.get("required_inputs")
        if isinstance(raw_inputs, list):
            seen_inputs: set[str] = set()
            merged_inputs = []
            forced_input_keys = (
                "title",
                "detail",
                "kind",
                "source",
                "automation",
                "format",
                "questions",
                "paths",
                "path_policy",
                "artifacts",
                "evidence_policy",
                "required",
                "advanced",
                "status",
                "answer",
            )
            for item in raw_inputs:
                if not isinstance(item, dict):
                    continue
                item_id = str(item.get("id") or "")
                seen_inputs.add(item_id)
                merged_inputs.append(dev_pipeline_merge_builtin_item(item, default_input_map.get(item_id, {}), forced_input_keys))
            for item_id, default_item in default_input_map.items():
                if item_id not in seen_inputs:
                    merged_inputs.append(deepcopy(default_item))
            template["required_inputs"] = merged_inputs
        else:
            template["required_inputs"] = default_inputs
        workers = [worker for worker in template.get("workers", []) if isinstance(worker, dict)]
        if not any(str(worker.get("id") or "") == str(template.get("selected_worker") or "") for worker in workers):
            template["selected_worker"] = str(workers[0].get("id") or "") if workers else ""
        return template

    if str(template.get("id") or "") != "generic-task":
        return template
    defaults = dev_pipeline_generic_blueprint_defaults()

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
            dev_pipeline_merge_default_fields(item, default_workers.get(str(item.get("id") or ""), {}))
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
            dev_pipeline_merge_default_fields(item, default_steps.get(str(item.get("id") or ""), {}))
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
            dev_pipeline_merge_default_fields(item, default_input_map.get(str(item.get("id") or ""), {}))
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
        HARD_PROREQ_TEMPLATE_ID: [
            {
                "id": "operator-thoughts",
                "title": "Operator thoughts and full plan",
                "detail": "Raw request, goals, constraints, assumptions, and complete plan text from the Run Pipeline prompt or questionnaire.",
                "kind": "questionnaire",
                "source": "user",
                "format": "structured answers",
                "artifacts": ["execution/hard-proreq/latest/operator_intake.json"],
                "evidence_policy": "Every hard proreq run must preserve the operator's source prompt and any questionnaire answers before model planning starts.",
                "questions": [
                    {"id": "intent", "prompt": "What are you trying to build or change?", "required": True, "answer_type": "text", "options": []},
                    {"id": "constraints", "prompt": "Which constraints, risks, or non-negotiables matter?", "required": False, "answer_type": "text", "options": []},
                    {"id": "done", "prompt": "What should be true when this project is done?", "required": True, "answer_type": "text", "options": []},
                ],
                "status": "missing",
                "required": True,
            },
            {
                "id": "generated-cento-context",
                "title": "Generated mini Cento context",
                "detail": "Cento-native gather-context, tool registry, repo search hits, and task-relevant files generated from the operator input.",
                "kind": "path",
                "source": "auto",
                "automation": "cento-context",
                "format": "JSON object",
                "paths": ["AGENTS.md", "README.md", "scripts/**", "templates/agent-work-app/**", "docs/**", "tests/**", "data/tools.json"],
                "path_policy": "Use Cento-native context before asking GPT pro to plan backend work.",
                "artifacts": ["execution/hard-proreq/latest/mini_cento_context.json"],
                "evidence_policy": "The Pro backend request must cite a lightweight Cento context artifact generated from the prompt.",
                "status": "configured",
                "required": True,
            },
            {
                "id": "ui-screenshot-request",
                "title": "Optional muted screenshot context",
                "detail": "Optional local screenshot path or generated frontend screenshot request split from the same operator input; this lane stays separate and muted in Execution Flow.",
                "kind": "image",
                "source": "auto",
                "automation": "openai-image",
                "muted": True,
                "blocking": False,
                "format": "prompt artifact",
                "image_refs": [
                    "workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/latest/existing_ui_reference.png",
                    "workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/latest/generated_integrator_screenshot.png",
                ],
                "image_notes": "Use an operator-provided local screenshot when present; otherwise generate or capture UI screenshots separately. Validate chunks against screenshot regions without giving backend planning frontend ownership.",
                "artifacts": [
                    "execution/hard-proreq/latest/ui_screenshot_request.json",
                    "workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/latest/existing_ui_reference.png",
                    "workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/latest/generated_integrator_screenshot.png",
                ],
                "evidence_policy": "Frontend visual work remains an optional muted lane and does not block backend story planning.",
                "status": "muted",
                "required": False,
            },
            {
                "id": "pro-backend-schema",
                "title": "GPT Pro backend schema manifest",
                "detail": "Strict JSON Schema used in the Responses API request and by generated Codex exec commands.",
                "kind": "details",
                "source": "auto",
                "automation": "schema-artifact",
                "format": "JSON Schema",
                "artifacts": ["execution/hard-proreq/latest/pro_output_schema.json", "execution/hard-proreq/latest/pro_backend_request.json"],
                "evidence_policy": "GPT Pro must return the backend plan through the lightweight hard proreq schema.",
                "status": "configured",
                "required": True,
            },
            {
                "id": "backend-work-handoff",
                "title": "10-story backend handoff",
                "detail": "Cento-native ten story manifests, parallel patch workset, manifest integration policy, validation plan, and Codex exec command scaffolding produced from the Pro output.",
                "kind": "evidence",
                "source": "auto",
                "automation": "evidence-handoff",
                "format": "artifact list",
                "artifacts": [
                    "execution/hard-proreq/latest/backend_work_manifest.json",
                    "execution/hard-proreq/latest/story_index.json",
                    "execution/hard-proreq/latest/parallel_patch_workset.json",
                    "execution/hard-proreq/latest/integration_plan.json",
                    "execution/hard-proreq/latest/validation_plan.json",
                    "execution/hard-proreq/latest/hard_proreq_evidence.json",
                ],
                "evidence_policy": "Backend work must be split into ten story manifests, owned paths, dependency order, validation commands, and handoff artifacts before parallel patch dispatch.",
                "status": "configured",
                "required": True,
            },
        ],
        MULTIPIPELINE_TEMPLATE_ID: [
            {
                "id": "multipipeline-objective",
                "title": "Multipipeline objective",
                "detail": "The operator goal, target areas, boundaries, and definition of success for the four sequential ProReq passes.",
                "kind": "questionnaire",
                "source": "user",
                "format": "structured answers",
                "artifacts": ["execution/multipipeline/latest/operator_intake.json"],
                "evidence_policy": "Every meta-pipeline run must preserve the operator objective before scheduling child ProReq pass requests.",
                "questions": [
                    {"id": "objective", "prompt": "What should this four-pass ProReq chain achieve?", "required": True, "answer_type": "long", "options": []},
                    {"id": "areas", "prompt": "Which areas, systems, or requirements should the four passes cover?", "required": True, "answer_type": "long", "options": []},
                    {"id": "boundaries", "prompt": "Which work, spend, dispatch, or repository changes are forbidden unless explicitly approved?", "required": True, "answer_type": "long", "options": []},
                    {"id": "handoff", "prompt": "What proves each pass produced usable guidance for the next pass?", "required": True, "answer_type": "long", "options": []},
                ],
                "status": "missing",
                "required": True,
            },
            {
                "id": "multipipeline-schedule-config",
                "title": "Sequential schedule controls",
                "detail": "Four-pass chain configuration: child pipeline, dispatch mode, UI screenshot request mode, Pro request mode, and guidance handoff policy.",
                "kind": "details",
                "source": "user",
                "format": "structured controls",
                "artifacts": ["inputs/multipipeline-proreq-chain_multipipeline-schedule-config.json", "execution/multipipeline/latest/multipipeline_schedule.json"],
                "evidence_policy": "The run must schedule exactly four ordered ProReq passes by default and keep live Pro/image execution opt-in.",
                "status": "provided",
                "required": True,
                "answer": "passes: 4\nchild_pipeline: hard-proreq-task\nexecution_mode: request-artifacts\nui_screenshot: request-artifact\npro_call: request-artifact\nhandoff_policy: previous-guidance-required",
            },
            {
                "id": "multipipeline-context",
                "title": "Generated Cento route context",
                "detail": "Cento-native tool registry, Dev Pipeline contract, ProReq route, parallel pipeline route, and repo context used by all four passes.",
                "kind": "path",
                "source": "auto",
                "automation": "cento-context",
                "format": "path list",
                "paths": ["AGENTS.md", "README.md", "scripts/**", "templates/agent-work-app/**", "docs/**", "tests/**", "data/tools.json", ".cento/api_workers.yaml"],
                "path_policy": "Use existing Cento routes and lowest-compute request artifacts before any live model dispatch.",
                "artifacts": ["execution/multipipeline/latest/multipipeline_schedule.json"],
                "evidence_policy": "Each ProReq pass request must cite the same Cento route context and previous pass guidance.",
                "status": "configured",
                "required": True,
            },
            {
                "id": "ui-screenshot-request",
                "title": "UI screenshot guidance request",
                "detail": "Auto-generated ChatGPT image prompt for the Dev Pipeline Studio UI showing the four sequential passes, Pro request, validation, and evidence handoff.",
                "kind": "image",
                "source": "auto",
                "automation": "openai-image-request",
                "muted": True,
                "blocking": False,
                "format": "prompt artifact",
                "image_refs": [],
                "image_notes": "Request-only by default; use an optional operator screenshot as style context when provided.",
                "artifacts": ["execution/multipipeline/latest/ui_screenshot_request.json"],
                "evidence_policy": "UI guidance remains a separate muted artifact and does not trigger live image generation unless the operator opts in.",
                "status": "muted",
                "required": False,
            },
            {
                "id": "multipipeline-pro-request",
                "title": "ChatGPT Pro chain request",
                "detail": "Strict prompt/request artifact asking ChatGPT Pro for manifests, integration guidance, validation guidance, next steps, and cost-aware model usage guidance.",
                "kind": "details",
                "source": "auto",
                "automation": "proreq-pro-request",
                "format": "JSON request artifact",
                "artifacts": ["execution/multipipeline/latest/chatgpt_pro_request.json"],
                "evidence_policy": "Live Pro dispatch is skipped unless explicitly enabled; the request artifact is still ready for ChatGPT Pro.",
                "status": "configured",
                "required": True,
            },
            {
                "id": "multipipeline-evidence",
                "title": "Sequential chain evidence",
                "detail": "Pass receipts, pass guidance artifacts, UI screenshot request, ChatGPT Pro request, roadmap, and validation summary.",
                "kind": "evidence",
                "source": "auto",
                "automation": "multipipeline-evidence-handoff",
                "format": "artifact bundle",
                "artifacts": [
                    "execution/multipipeline/latest/multipipeline_schedule.json",
                    "execution/multipipeline/latest/pass_01_guidance.json",
                    "execution/multipipeline/latest/pass_02_guidance.json",
                    "execution/multipipeline/latest/pass_03_guidance.json",
                    "execution/multipipeline/latest/pass_04_guidance.json",
                    "execution/multipipeline/latest/chain_roadmap.md",
                    "execution/multipipeline/latest/multipipeline_evidence.json",
                ],
                "evidence_policy": "A meta-pipeline run is complete only when all four pass requests and the final evidence handoff exist.",
                "status": "configured",
                "required": True,
            },
        ],
        PARALLEL_PIPELINE_TEMPLATE_ID: [
            {
                "id": "parallel-objective",
                "title": "Parallel pipeline objective",
                "detail": "Operator goal, acceptance criteria, risk limits, and completion definition for this parallel workset run.",
                "kind": "questionnaire",
                "source": "user",
                "format": "structured answers",
                "artifacts": ["execution/parallel/latest/objective.json"],
                "evidence_policy": "Every parallel run must preserve the objective before workset generation and worker dispatch.",
                "questions": [
                    {"id": "goal", "prompt": "What should the parallel pipeline change or produce?", "required": True, "answer_type": "text", "options": []},
                    {"id": "acceptance", "prompt": "What proves each worker and the integrator succeeded?", "required": True, "answer_type": "text", "options": []},
                    {"id": "risks", "prompt": "Which risks or forbidden changes should block dispatch?", "required": False, "answer_type": "text", "options": []},
                ],
                "status": "missing",
                "required": True,
            },
            {
                "id": "parallel-workstreams",
                "title": "Advanced workstream override",
                "detail": "Optional expert override. Leave collapsed so Cento can generate worker lanes and exclusive write paths from the objective.",
                "kind": "path",
                "source": "user",
                "format": "optional path list or JSON workstreams",
                "paths": [],
                "path_policy": "When supplied, every path must be exclusive to one worker. Shared-file or overlapping path work belongs in the serialized integrator step, not parallel workers.",
                "artifacts": ["execution/worksets/latest.json", "execution/worksets/<run-id>.json"],
                "evidence_policy": "The generated workset makes write_paths explicit before any worker is allowed to run.",
                "status": "configured",
                "required": False,
                "advanced": True,
            },
            {
                "id": "parallel-read-context",
                "title": "Generated parallel read context",
                "detail": "Cento-native read paths, tool contracts, API worker config, and repo context used by all parallel workers.",
                "kind": "path",
                "source": "auto",
                "automation": "cento-context",
                "format": "path list",
                "paths": ["AGENTS.md", "README.md", "scripts/**", "templates/agent-work-app/**", "docs/**", "tests/**", "data/tools.json", ".cento/api_workers.yaml"],
                "path_policy": "Shared read context is allowed; writes remain exclusive per worker.",
                "artifacts": ["inputs/parallel-pipeline_parallel-read-context.json"],
                "evidence_policy": "Workers must receive a common read context and never infer extra write scope.",
                "status": "configured",
                "required": True,
            },
            {
                "id": "parallel-ui-config",
                "title": "Parallel UI and runtime config",
                "detail": "Max parallelism, runtime profile, budget, validation mode, and Execution Flow display policy for the parallel run.",
                "kind": "details",
                "source": "user",
                "format": "structured controls",
                "artifacts": ["inputs/parallel-pipeline_parallel-ui-config.json", "execution/parallel_execution_manifest.json"],
                "evidence_policy": "Execution UI must show worker fan-out, max parallelism, serialized integration, validation, and evidence convergence.",
                "status": "provided",
                "required": True,
                "answer": "max_parallel: 10\nruntime: fixture\nintegrator: sequential\nvalidation: smoke\napply_mode: dry-run\nbudget_usd: 0.00\nmax_budget_usd: 0.00",
            },
            {
                "id": "parallel-integrator-gate",
                "title": "Serialized integration gate",
                "detail": "Auto-generated evidence contract proving that worker patches converge through a single sequential integrator.",
                "kind": "evidence",
                "source": "auto",
                "automation": "sequential-integrator",
                "format": "receipt list",
                "artifacts": [".cento/worksets/*/workset_receipt.json", ".cento/worksets/*/integration/**", "integration_receipts/*.json"],
                "evidence_policy": "Parallel workers may run concurrently, but all accepted patches must be applied through one serialized integration lane.",
                "status": "configured",
                "required": True,
            },
            {
                "id": "parallel-validation-evidence",
                "title": "Parallel validation and handoff evidence",
                "detail": "Validator receipts, worker receipts, costs, changed paths, logs, and residual risk notes for review.",
                "kind": "evidence",
                "source": "auto",
                "automation": "parallel-evidence-handoff",
                "format": "artifact bundle",
                "artifacts": ["validation/validation_receipt.json", "evidence/evidence_bundle.json", "execution/delivery/<run-id>/workset.stdout.log", "execution/delivery/<run-id>/workset.stderr.log"],
                "evidence_policy": "A run is reviewable only when worker outcomes, integration receipts, validation receipts, and cost facts are linked.",
                "status": "configured",
                "required": True,
            },
        ],
        PATCH_SWARM_TEMPLATE_ID: [
            {
                "id": "patch-swarm-objective",
                "title": "Patch Swarm objective",
                "detail": "Operator goal, acceptance criteria, risk limits, and the target patch market outcome.",
                "kind": "questionnaire",
                "source": "user",
                "format": "structured answers",
                "artifacts": ["execution/patch-swarm/latest/patch_swarm_manifest.json"],
                "evidence_policy": "Every Patch Swarm run must preserve the objective before ProReq lane dispatch.",
                "questions": [
                    {"id": "goal", "prompt": "What should the patch swarm improve or build?", "required": True, "answer_type": "text", "options": []},
                    {"id": "acceptance", "prompt": "What proves a candidate patch is worth integrating?", "required": True, "answer_type": "text", "options": []},
                    {"id": "risk", "prompt": "Which files, costs, or behaviors must block candidates?", "required": False, "answer_type": "text", "options": []},
                ],
                "status": "missing",
                "required": True,
            },
            {
                "id": "patch-swarm-provider-policy",
                "title": "Provider and cost policy",
                "detail": "Provider mix, candidate target, max active agents, live/fixture mode, and budget controls.",
                "kind": "details",
                "source": "user",
                "format": "structured controls",
                "artifacts": ["execution/patch-swarm/latest/cost_policy.json"],
                "evidence_policy": "Provider and budget policy must be visible before any live model or local agent dispatch.",
                "status": "provided",
                "required": True,
                "answer": "candidate_target: 100\nmax_parallel_agents: 5\nproviders: codex-exec,claude-code,api-openai\nmode: fixture\nbudget_usd: 0.00\nmax_budget_usd: 0.00",
            },
            {
                "id": "patch-swarm-runtime-context",
                "title": "Runtime adapter context",
                "detail": "Cento runtime profiles, API worker schema, Workset materializer, and Safe Integrator context.",
                "kind": "path",
                "source": "auto",
                "automation": "cento-context",
                "format": "path list",
                "paths": ["scripts/parallel_delivery.py", "scripts/cento_workset.py", "scripts/cento_openai_worker.py", ".cento/runtimes.yaml", ".cento/api_workers.yaml", "templates/agent-work-app/**"],
                "path_policy": "Providers must converge on candidate_patch.v1 and never mutate the operator worktree directly.",
                "artifacts": ["execution/patch-swarm/latest/proreq_execution_manifest.json"],
                "evidence_policy": "Runtime adapters must be listed in the manifest before candidates are generated.",
                "status": "configured",
                "required": True,
            },
            {
                "id": "patch-swarm-integrator-gate",
                "title": "Dedicated integrator gate",
                "detail": "One serialized integration execution consumes all ten ProReq lane outputs and selects winners.",
                "kind": "evidence",
                "source": "auto",
                "automation": "safe-integrator-handoff",
                "format": "artifact bundle",
                "artifacts": ["execution/patch-swarm/latest/integration_execution.json", "execution/patch-swarm/latest/safe_integrator_handoff.json"],
                "evidence_policy": "A run is reviewable only after the dedicated integrator writes a Safe Integrator handoff.",
                "status": "configured",
                "required": True,
            },
            {
                "id": "patch-swarm-validation-evidence",
                "title": "Candidate validation and ranking evidence",
                "detail": "Candidate index, dedupe clusters, ranking, cost ledger, validation summary, and residual risks.",
                "kind": "evidence",
                "source": "auto",
                "automation": "patch-swarm-validation",
                "format": "artifact bundle",
                "artifacts": ["execution/patch-swarm/latest/candidate_index.json", "execution/patch-swarm/latest/ranking.json", "execution/patch-swarm/latest/validation_summary.json"],
                "evidence_policy": "Candidate count, provider mix, validation, ranking, and cost facts must be visible in the UI.",
                "status": "configured",
                "required": True,
            },
        ],
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
    defaults[PROREQ_LIGHT_TEMPLATE_ID] = deepcopy(defaults[HARD_PROREQ_TEMPLATE_ID])
    for item in defaults[PROREQ_LIGHT_TEMPLATE_ID]:
        if not isinstance(item, dict):
            continue
        if item.get("id") == "generated-cento-context":
            item["path_policy"] = "Use Cento-native context before asking Codex Exec to simulate the Pro planning lane."
            item["evidence_policy"] = "The Codex Exec ProReq-light prompt must cite a lightweight Cento context artifact generated from the operator prompt."
        elif item.get("id") == "pro-backend-schema":
            item["title"] = "Codex Exec ProReq schema manifest"
            item["detail"] = "Strict JSON Schema used by the Codex Exec prompt that replaces the live Pro request."
            item["automation"] = "codex-exec-schema-artifact"
            item["artifacts"] = [
                "execution/hard-proreq/latest/pro_output_schema.json",
                "execution/hard-proreq/latest/proreq_light_output_schema.json",
                "execution/hard-proreq/latest/pro_backend_request.json",
                "execution/hard-proreq/latest/proreq_light_codex_prompt.md",
            ]
            item["evidence_policy"] = "Codex Exec should return the backend plan through the same lightweight hard proreq schema as the Pro route."
        elif item.get("id") == "backend-work-handoff":
            item["detail"] = "Cento-native ten story manifests, parallel patch workset, manifest integration policy, validation plan, and Codex exec command scaffolding produced from the ProReq-light Codex Exec output."
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
            "source": str(item.get("source") or "user"),
            "automation": str(item.get("automation") or item.get("automation_source") or ""),
            "automation_source": str(item.get("automation_source") or item.get("automation") or ""),
            "muted": bool(item.get("muted", False)),
            "blocking": bool(item.get("blocking", True)),
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
                "source": str(item.get("source") or "user"),
                "automation": str(item.get("automation") or item.get("automation_source") or ""),
                "muted": bool(item.get("muted", False)),
                "blocking": bool(item.get("blocking", True)),
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
                "source": str(item.get("source") or "user"),
                "automation": str(item.get("automation") or item.get("automation_source") or ""),
                "muted": bool(item.get("muted", False)),
                "blocking": bool(item.get("blocking", True)),
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


def dev_pipeline_execution_stage_status(items: list[dict[str, Any]]) -> str:
    statuses = {str(item.get("status") or "").lower().replace(" ", "-") for item in items if isinstance(item, dict)}
    if not statuses:
        return "configured"
    if statuses & {"failed"}:
        return "failed"
    if statuses & {"blocked", "rejected", "budget-blocked", "budget-exceeded", "dependency-blocked"}:
        return "blocked"
    if statuses & {"running", "active", "in-progress"}:
        return "running"
    if statuses & {"queued", "configured", "pending"}:
        return "queued"
    if statuses <= {"accepted", "applied", "completed", "passed", "merged", "muted", "separate-flow", "deferred"}:
        return "completed"
    return "configured"


def dev_pipeline_execution_status_label(value: Any) -> str:
    raw = str(value or "configured").lower().replace("_", "-").replace(" ", "-")
    if raw in {"accepted", "applied", "passed", "merged"}:
        return "completed"
    if raw in {"muted", "separate-flow", "deferred"}:
        return "muted"
    if raw in {"active", "in-progress"}:
        return "running"
    if raw in {"budget-blocked", "budget-exceeded", "dependency-blocked"}:
        return "blocked"
    if raw in {"completed", "running", "queued", "failed", "blocked", "rejected", "configured", "muted"}:
        return raw
    return "configured"


def dev_pipeline_execution_command_for_step(step_id: str) -> list[str]:
    commands = {
        "checkout-branch": ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        "snapshot-repo-state": ["git", "status", "--short"],
        "apply-change-units": ["python3", "-m", "json.tool", "workspace/runs/dev-pipeline-studio/docs-pages/latest/workset.json"],
        "run-formatters": ["node", "--check", "templates/agent-work-app/app.js"],
        "run-focused-tests": ["python3", "-m", "py_compile", "scripts/agent_work_app.py"],
        "run-full-tests": ["python3", "-m", "py_compile", "workspace/runs/agent-work/dev-pipeline-studio-execution-flow/assert_execution_flow.py"],
        "collect-diff": ["git", "diff", "--stat"],
        "collect-logs": ["python3", "scripts/story_manifest.py", "validate", "workspace/runs/agent-work/drafts/dev-pipeline-studio-execution-flow/story.json"],
        "new-execution-step": ["python3", "-m", "json.tool", "workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/execution_manifest.json"],
        "collect-operator-intake": ["python3", "scripts/dev_pipeline_hard_proreq.py", "intake"],
        "build-cento-context": ["python3", "scripts/dev_pipeline_hard_proreq.py", "context"],
        "write-ui-screenshot-request": ["python3", "scripts/dev_pipeline_hard_proreq.py", "screenshot"],
        "prepare-pro-backend-request": ["python3", "scripts/dev_pipeline_hard_proreq.py", "pro-request"],
        "dispatch-pro-backend-plan": ["python3", "scripts/dev_pipeline_hard_proreq.py", "pro-plan"],
        "dispatch-codex-pro-backend-plan": ["python3", "scripts/dev_pipeline_hard_proreq.py", "codex-pro-plan"],
        "materialize-backend-work": ["python3", "scripts/dev_pipeline_hard_proreq.py", "backend-work"],
        "write-integration-plan": ["python3", "scripts/dev_pipeline_hard_proreq.py", "integration-plan"],
        "write-validation-plan": ["python3", "scripts/dev_pipeline_hard_proreq.py", "validation-plan"],
        "collect-proreq-evidence": ["python3", "scripts/dev_pipeline_hard_proreq.py", "evidence"],
        "collect-multipipeline-intake": ["python3", "scripts/dev_pipeline_multipipeline.py", "intake"],
        "write-multipipeline-schedule": ["python3", "scripts/dev_pipeline_multipipeline.py", "schedule"],
        "run-proreq-pass-1": ["python3", "scripts/dev_pipeline_multipipeline.py", "pass-1"],
        "run-proreq-pass-2": ["python3", "scripts/dev_pipeline_multipipeline.py", "pass-2"],
        "run-proreq-pass-3": ["python3", "scripts/dev_pipeline_multipipeline.py", "pass-3"],
        "run-proreq-pass-4": ["python3", "scripts/dev_pipeline_multipipeline.py", "pass-4"],
        "write-multipipeline-ui-screenshot-request": ["python3", "scripts/dev_pipeline_multipipeline.py", "ui-screenshot-request"],
        "write-multipipeline-pro-request": ["python3", "scripts/dev_pipeline_multipipeline.py", "pro-request"],
        "collect-multipipeline-evidence": ["python3", "scripts/dev_pipeline_multipipeline.py", "evidence"],
    }
    return commands.get(step_id, ["python3", "-m", "json.tool", "workspace/runs/dev-pipeline-studio/docs-pages/latest/pipeline_manifest.json"])


def dev_pipeline_execution_steps(root: Path, template: dict[str, Any]) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
    execution_manifest_rel = str(template.get("execution_manifest") or "execution/execution_manifest.json")
    execution_manifest = dev_pipeline_artifact_json(root, execution_manifest_rel)
    execution_steps = [item for item in execution_manifest.get("steps", []) if isinstance(item, dict)]
    if not execution_steps:
        execution_steps = [
            {
                "id": str(item.get("id") or ""),
                "title": str(item.get("title") or item.get("id") or ""),
                "file": str(item.get("file") or ""),
                "status": str(item.get("status") or "queued"),
                "dependencies": [str(value) for value in item.get("dependencies", []) if isinstance(value, str)],
                "config": str(item.get("integration_config") or ""),
                "receipt": str(item.get("integration_receipt") or ""),
            }
            for item in template.get("factory_steps", [])
            if isinstance(item, dict)
        ]
    if not execution_steps:
        raise AgentWorkAppError("No execution steps are configured for this pipeline template")
    return execution_manifest_rel, execution_manifest, execution_steps


def dev_pipeline_template_factory_steps(template: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": str(item.get("id") or ""),
            "title": str(item.get("title") or item.get("id") or ""),
            "file": str(item.get("file") or ""),
            "status": str(item.get("status") or "queued"),
            "mode": str(item.get("mode") or ""),
            "muted": bool(item.get("muted")),
            "lane": str(item.get("lane") or ""),
            "dependencies": [str(value) for value in item.get("dependencies", []) if isinstance(value, str)],
            "config": str(item.get("integration_config") or item.get("config") or ""),
            "receipt": str(item.get("integration_receipt") or item.get("receipt") or ""),
        }
        for item in template.get("factory_steps", [])
        if isinstance(item, dict)
    ]


def dev_pipeline_write_execution_state(
    root: Path,
    execution_manifest_rel: str,
    execution_manifest: dict[str, Any],
    run_payload: dict[str, Any],
) -> None:
    run_id = str(run_payload.get("run_id") or "").strip()
    updated_manifest = {
        **execution_manifest,
        "schema_version": "cento.execution_manifest.v1",
        "source": str(run_payload.get("source") or "cento-workset-api-openai"),
        "pipeline": str(run_payload.get("pipeline") or ""),
        "run_id": run_id,
        "run_started_at": str(run_payload.get("started_at") or ""),
        "run_finished_at": str(run_payload.get("finished_at") or ""),
        "status": str(run_payload.get("status") or "running"),
        "steps": [item for item in run_payload.get("steps", []) if isinstance(item, dict)],
        "written_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json_path(dev_pipeline_root_path(root, execution_manifest_rel), updated_manifest)
    write_json_path(dev_pipeline_root_path(root, "execution/execution_run.json"), run_payload)
    if run_id and "/" not in run_id and "\\" not in run_id:
        write_json_path(dev_pipeline_root_path(root, f"execution/runs/{run_id}.json"), run_payload)


def dev_pipeline_execution_history(root: Path, active_run_id: str = "", pipeline: str = "") -> list[dict[str, Any]]:
    runs_root = root / "execution" / "runs"
    rows: list[dict[str, Any]] = []
    if runs_root.exists():
        for path in sorted(runs_root.glob("*.json"), key=lambda item: item.stat().st_mtime if item.exists() else 0, reverse=True):
            payload = read_json_path(path)
            if pipeline and str(payload.get("pipeline") or "") != pipeline:
                continue
            run_id = str(payload.get("run_id") or path.stem)
            if not run_id:
                continue
            started_at = parse_iso_datetime(payload.get("started_at"))
            finished_at = parse_iso_datetime(payload.get("finished_at"))
            run_artifacts = [item for item in payload.get("artifacts", []) if isinstance(item, dict)]
            rows.append(
                {
                    "run_id": run_id,
                    "status": dev_pipeline_execution_status_label(payload.get("status")),
                    "started": format_run_time(started_at) if started_at else "",
                    "finished": format_run_time(finished_at) if finished_at else "In progress",
                    "duration": duration_label(int(float(payload.get("duration_seconds") or 0))),
                    "source": str(payload.get("source") or "real-e2e"),
                    "pipeline": str(payload.get("pipeline") or ""),
                    "active": run_id == active_run_id,
                    "path": dev_pipeline_relative(path),
                    "artifact_count": len(run_artifacts),
                    "ready_artifact_count": len([item for item in run_artifacts if bool(item.get("exists", True))]),
                }
            )
    return rows[:24]


def dev_pipeline_seed_execution_e2e(
    root: Path,
    manifest: dict[str, Any],
    project: dict[str, Any],
    template: dict[str, Any],
    trigger: dict[str, Any] | None = None,
) -> dict[str, Any]:
    execution_manifest_rel, execution_manifest, execution_steps = dev_pipeline_execution_steps(root, template)
    trigger = trigger if isinstance(trigger, dict) else {}

    run_started = datetime.now(timezone.utc)
    run_id = f"{template.get('id') or 'pipeline'}-{project.get('id') or 'project'}-{run_started.strftime('%Y%m%dT%H%M%S%fZ')}"
    queued_steps: list[dict[str, Any]] = []
    for index, step in enumerate(execution_steps, start=1):
        step_id = str(step.get("id") or f"step-{index}")
        title = str(step.get("title") or step_id)
        command = dev_pipeline_execution_command_for_step(step_id)
        queued_steps.append(
            {
                **step,
                "id": step_id,
                "title": title,
                "status": "queued",
                "command": shlex.join(command),
                "exit_code": None,
                "duration": "0s",
                "duration_seconds": 0,
                "started_at": "",
                "finished_at": "",
                "stdout_tail": "",
                "stderr_tail": "",
            }
        )
    run_payload = {
        "schema_version": "cento.execution_run.v1",
        "source": "real-e2e",
        "run_id": run_id,
        "pipeline": f"{template.get('id') or 'pipeline'}-{project.get('id') or 'project'}",
        "status": "running",
        "started_at": run_started.isoformat(),
        "finished_at": "",
        "duration_seconds": 0,
        "triggered_by": str(trigger.get("triggered_by") or "prompt-router"),
        "issue_id": str(trigger.get("issue_id") or ""),
        "issue_subject": str(trigger.get("issue_subject") or ""),
        "prompt": str(trigger.get("prompt") or "")[:2000],
        "stages": [
            {"id": "input", "started_at": run_started.isoformat(), "finished_at": (run_started + timedelta(seconds=1)).isoformat(), "status": "completed"},
            {"id": "repo", "started_at": (run_started + timedelta(seconds=1)).isoformat(), "finished_at": (run_started + timedelta(seconds=2)).isoformat(), "status": "completed"},
            {"id": "blueprint", "started_at": (run_started + timedelta(seconds=2)).isoformat(), "finished_at": (run_started + timedelta(seconds=3)).isoformat(), "status": "completed"},
            {"id": "factory", "started_at": run_started.isoformat(), "finished_at": "", "status": "running"},
            {"id": "validation", "started_at": "", "finished_at": "", "status": "queued"},
            {"id": "handoff", "started_at": "", "finished_at": "", "status": "queued"},
        ],
        "steps": queued_steps,
        "logs": [
            {
                "timestamp": run_started.isoformat(),
                "stage": "execution",
                "source": "pipeline",
                "message": str(trigger.get("message") or "Live E2E execution started"),
            }
        ],
        "written_at": datetime.now(timezone.utc).isoformat(),
    }
    dev_pipeline_write_execution_state(root, execution_manifest_rel, execution_manifest, run_payload)
    return run_payload


def dev_pipeline_finish_execution_e2e(root: Path, project_id: str, template_id: str, run_id: str) -> None:
    with DEV_PIPELINE_EXECUTION_LOCK:
        manifest_path = root / "pipeline_manifest.json"
        manifest = read_json_path(manifest_path)
        if not manifest:
            return
        templates = [item for item in manifest.get("templates", []) if isinstance(item, dict)]
        projects = [item for item in manifest.get("projects", []) if isinstance(item, dict)]
        project = dev_pipeline_find(projects, project_id, project_id)
        template = dev_pipeline_find(templates, template_id, template_id)
        if not project or not template:
            return
        dev_pipeline_apply_generic_blueprint(template)
        execution_manifest_rel, execution_manifest, execution_steps = dev_pipeline_execution_steps(root, template)
        run_payload = dev_pipeline_artifact_json(root, "execution/execution_run.json")
        if str(run_payload.get("run_id") or "") != run_id:
            return
        run_started = parse_iso_datetime(run_payload.get("started_at")) or datetime.now(timezone.utc)
        run_events = [item for item in run_payload.get("logs", []) if isinstance(item, dict)]
        updated_steps = [item for item in run_payload.get("steps", []) if isinstance(item, dict)]
        if len(updated_steps) != len(execution_steps):
            updated_steps = [
                {
                    **step,
                    "id": str(step.get("id") or f"step-{index}"),
                    "title": str(step.get("title") or step.get("id") or f"step-{index}"),
                    "status": "queued",
                    "command": shlex.join(dev_pipeline_execution_command_for_step(str(step.get("id") or f"step-{index}"))),
                    "exit_code": None,
                    "duration": "0s",
                    "duration_seconds": 0,
                    "started_at": "",
                    "finished_at": "",
                    "stdout_tail": "",
                    "stderr_tail": "",
                }
                for index, step in enumerate(execution_steps, start=1)
            ]

        run_failed = False
        for index, step in enumerate(updated_steps):
            step_id = str(step.get("id") or f"step-{index + 1}")
            title = str(step.get("title") or step_id)
            command = dev_pipeline_execution_command_for_step(step_id)
            started = datetime.now(timezone.utc)
            updated_steps[index] = {
                **step,
                "id": step_id,
                "title": title,
                "status": "running",
                "command": shlex.join(command),
                "started_at": started.isoformat(),
                "finished_at": "",
                "stdout_tail": "",
                "stderr_tail": "",
            }
            run_payload["status"] = "running"
            run_payload["steps"] = updated_steps
            run_payload["logs"] = [
                *run_events,
                {
                    "timestamp": started.isoformat(),
                    "stage": "execution",
                    "source": step_id,
                    "message": f"{title} started",
                    "command": shlex.join(command),
                },
            ]
            run_payload["written_at"] = datetime.now(timezone.utc).isoformat()
            dev_pipeline_write_execution_state(root, execution_manifest_rel, execution_manifest, run_payload)

            result = subprocess.run(command, cwd=ROOT_DIR, text=True, capture_output=True, timeout=30)
            elapsed = (datetime.now(timezone.utc) - started).total_seconds()
            if elapsed < DEV_PIPELINE_EXECUTION_MIN_STEP_SECONDS:
                time.sleep(DEV_PIPELINE_EXECUTION_MIN_STEP_SECONDS - elapsed)
            finished = datetime.now(timezone.utc)
            duration_seconds = max(1, int(round((finished - started).total_seconds())))
            status = "completed" if result.returncode == 0 else "failed"
            if result.returncode != 0:
                run_failed = True
            updated_steps[index] = {
                **step,
                "id": step_id,
                "title": title,
                "status": status,
                "command": shlex.join(command),
                "exit_code": result.returncode,
                "duration": duration_label(duration_seconds),
                "duration_seconds": duration_seconds,
                "started_at": started.isoformat(),
                "finished_at": finished.isoformat(),
                "stdout_tail": result.stdout[-1200:],
                "stderr_tail": result.stderr[-1200:],
            }
            run_events.append(
                {
                    "timestamp": started.isoformat(),
                    "stage": "execution",
                    "source": step_id,
                    "message": f"{title} executed: {status}",
                    "command": shlex.join(command),
                    "exit_code": result.returncode,
                }
            )
            run_payload["status"] = "failed" if run_failed else "running"
            run_payload["steps"] = updated_steps
            run_payload["logs"] = run_events
            run_payload["written_at"] = datetime.now(timezone.utc).isoformat()
            dev_pipeline_write_execution_state(root, execution_manifest_rel, execution_manifest, run_payload)
            if run_failed:
                break

        if run_failed:
            for index in range(index + 1, len(updated_steps)):
                step = updated_steps[index]
                updated_steps[index] = {
                    **step,
                    "status": "blocked",
                    "exit_code": None,
                    "duration": "0s",
                    "duration_seconds": 0,
                    "started_at": "",
                    "finished_at": "",
                    "stdout_tail": "",
                    "stderr_tail": "Skipped because an upstream execution step failed.",
                }

    finished_values = [parse_iso_datetime(step.get("finished_at")) for step in updated_steps]
    run_finished = max((value for value in finished_values if value is not None), default=datetime.now(timezone.utc))
    run_status = "failed" if run_failed else "completed"
    factory_started = parse_iso_datetime(updated_steps[0].get("started_at")) or run_started
    factory_finished = max((parse_iso_datetime(step.get("finished_at")) or factory_started for step in updated_steps), default=factory_started)
    stages = [
        {"id": "input", "started_at": run_started.isoformat(), "finished_at": (run_started + timedelta(seconds=1)).isoformat(), "status": "completed"},
        {"id": "repo", "started_at": (run_started + timedelta(seconds=1)).isoformat(), "finished_at": (run_started + timedelta(seconds=2)).isoformat(), "status": "completed"},
        {"id": "blueprint", "started_at": (run_started + timedelta(seconds=2)).isoformat(), "finished_at": (run_started + timedelta(seconds=3)).isoformat(), "status": "completed"},
        {"id": "factory", "started_at": factory_started.isoformat(), "finished_at": factory_finished.isoformat(), "status": run_status},
        {"id": "validation", "started_at": factory_finished.isoformat(), "finished_at": run_finished.isoformat(), "status": run_status},
        {"id": "handoff", "started_at": run_finished.isoformat(), "finished_at": run_finished.isoformat(), "status": run_status},
    ]
    run_payload["status"] = run_status
    run_payload["finished_at"] = run_finished.isoformat()
    run_payload["duration_seconds"] = max(0, int(round((run_finished - run_started).total_seconds())))
    run_payload["stages"] = stages
    run_payload["steps"] = updated_steps
    run_payload["logs"] = run_events
    run_payload["written_at"] = datetime.now(timezone.utc).isoformat()
    dev_pipeline_write_execution_state(root, execution_manifest_rel, execution_manifest, run_payload)

    manifest["active_run_id"] = run_id
    manifest["status"] = run_status
    manifest["status_detail"] = "Execution Flow live E2E completed; execution manifest, run receipt, timestamps, logs, and animation source are in sync"
    write_json_path(manifest_path, manifest)
    dev_pipeline_append_event(
        root,
        manifest,
        "pipeline_run_execution_e2e_finished",
        str(project.get("id") or project_id),
        str(template.get("id") or template_id),
        {"execution_run_id": run_id, "status": run_status},
    )


def dev_pipeline_spawn_execution_e2e(root: Path, project_id: str, template_id: str, run_id: str) -> None:
    thread = threading.Thread(
        target=dev_pipeline_finish_execution_e2e,
        args=(root, project_id, template_id, run_id),
        name=f"dev-pipeline-execution-{run_id}",
        daemon=True,
    )
    thread.start()


DEV_PIPELINE_DELIVERY_BUDGET_USD = float(os.environ.get("CENTO_PIPELINE_DELIVERY_BUDGET_USD", "10.00"))
DEV_PIPELINE_DELIVERY_MAX_BUDGET_USD = float(os.environ.get("CENTO_PIPELINE_DELIVERY_MAX_BUDGET_USD", "20.00"))
DEV_PIPELINE_DELIVERY_API_PROFILE = os.environ.get("CENTO_PIPELINE_DELIVERY_API_PROFILE", "api-section-worker")
DEV_PIPELINE_DELIVERY_OUTPUT_SCHEMA = "patch_proposal.v1"
DEV_PIPELINE_DELIVERY_TIMEOUT_SECONDS = int(os.environ.get("CENTO_PIPELINE_DELIVERY_TIMEOUT_SECONDS", "90"))
DEV_PIPELINE_DELIVERY_REDIRECT_GRACE_SECONDS = float(os.environ.get("CENTO_PIPELINE_DELIVERY_REDIRECT_GRACE_SECONDS", "2.5"))
DEV_PIPELINE_INTEGRATION_MODEL_CEILING = os.environ.get("CENTO_PIPELINE_INTEGRATION_MODEL_CEILING", "gpt-4.1-mini")
DEV_PIPELINE_PATH_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9_./-])(?:(?:[A-Za-z0-9_.@+-]+/)+[A-Za-z0-9_.@+-]+|"
    r"[A-Za-z0-9][A-Za-z0-9_.@+-]*\.(?:py|js|jsx|ts|tsx|css|html|md|json|txt|ya?ml|toml|sh|sql|svg|csv|xml))(?![A-Za-z0-9_./-])"
)
DEV_PIPELINE_QUOTED_TOKEN_RE = re.compile(r"`([^`]+)`|\"([^\"]+)\"|'([^']+)'")
DEV_PIPELINE_PROTECTED_WRITE_PREFIXES = (
    ".git",
    ".env",
    "node_modules",
    "experimental/redmine-career-consulting/data/postgres",
)


def dev_pipeline_workset_slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")[:52] or "task"


def dev_pipeline_env_reference(value: str) -> str:
    match = re.fullmatch(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-(.*))?\}", str(value or "").strip())
    if not match:
        return str(value or "").strip()
    return os.environ.get(match.group(1), match.group(2) or "").strip()


def dev_pipeline_api_worker_config() -> tuple[dict[str, Any], list[str]]:
    path = ROOT_DIR / ".cento" / "api_workers.yaml"
    errors: list[str] = []
    if not path.exists():
        return {}, [f"API worker config is missing: {dev_pipeline_relative(path)}"]
    try:
        import yaml  # type: ignore

        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        return {}, [f"API worker config could not be loaded: {exc}"]
    if not isinstance(payload, dict):
        return {}, ["API worker config must be a mapping"]
    openai_config = payload.get("openai") if isinstance(payload.get("openai"), dict) else {}
    if openai_config.get("enabled") is False:
        errors.append("OpenAI API workers are disabled in .cento/api_workers.yaml")
    profiles = payload.get("profiles") if isinstance(payload.get("profiles"), dict) else {}
    profile = profiles.get(DEV_PIPELINE_DELIVERY_API_PROFILE) if isinstance(profiles.get(DEV_PIPELINE_DELIVERY_API_PROFILE), dict) else {}
    if not profile:
        errors.append(f"API worker profile is missing: {DEV_PIPELINE_DELIVERY_API_PROFILE}")
    model = dev_pipeline_env_reference(str(profile.get("model") or ""))
    if not model:
        errors.append(f"API worker model is not configured for profile {DEV_PIPELINE_DELIVERY_API_PROFILE}")
    if not os.environ.get("OPENAI_API_KEY"):
        errors.append("OPENAI_API_KEY is not set")
    return payload, errors


def dev_pipeline_clean_target_path(candidate: str) -> str:
    value = str(candidate or "").strip().strip(".,;:()[]{}<>")
    value = value.replace("\\", "/").lstrip("./")
    if not value or "://" in value or "*" in value or value.startswith("#"):
        return ""
    if Path(value).is_absolute():
        try:
            value = Path(value).resolve().relative_to(ROOT_DIR.resolve()).as_posix()
        except ValueError:
            return ""
    parts = [part for part in value.split("/") if part]
    if not parts or any(part == ".." for part in parts):
        return ""
    normalized = "/".join(parts)
    if any(normalized == prefix or normalized.startswith(f"{prefix}/") for prefix in DEV_PIPELINE_PROTECTED_WRITE_PREFIXES):
        return ""
    path = ROOT_DIR / normalized
    if path.exists() and path.is_dir():
        return ""
    has_file_suffix = bool(Path(normalized).suffix)
    if not has_file_suffix and not path.is_file():
        return ""
    return normalized


def dev_pipeline_extract_target_paths_from_text(text: str) -> list[str]:
    candidates: list[str] = []
    for match in DEV_PIPELINE_QUOTED_TOKEN_RE.finditer(str(text or "")):
        raw = next((group for group in match.groups() if group), "")
        if raw:
            candidates.append(raw)
    candidates.extend(match.group(0) for match in DEV_PIPELINE_PATH_TOKEN_RE.finditer(str(text or "")))
    paths: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        clean = dev_pipeline_clean_target_path(candidate)
        if clean and clean not in seen:
            seen.add(clean)
            paths.append(clean)
    return paths


def dev_pipeline_delivery_prompt(project: dict[str, Any], template: dict[str, Any], trigger: dict[str, Any]) -> str:
    prompt_parts = [
        str(trigger.get("prompt") or "").strip(),
        str(trigger.get("issue_subject") or "").strip(),
        str(trigger.get("message") or "").strip(),
    ]
    previous = dev_pipeline_artifact_json(DEV_PIPELINE_STUDIO_ROOT, "execution/execution_run.json")
    if not any(prompt_parts):
        prompt_parts.extend([str(previous.get("prompt") or ""), str(previous.get("issue_subject") or "")])
    for item in template.get("required_inputs", []):
        if not isinstance(item, dict):
            continue
        prompt_parts.extend(
            [
                str(item.get("answer") or ""),
                " ".join(str(value) for value in item.get("answer_values", []) if isinstance(value, str)),
                " ".join(str(value) for value in item.get("paths", []) if isinstance(value, str)),
            ]
        )
    prompt = "\n\n".join(part for part in prompt_parts if part)
    if not prompt:
        prompt = str(template.get("description") or project.get("surface") or "").strip()
    return prompt[:8000]


def dev_pipeline_delivery_target_paths(project: dict[str, Any], template: dict[str, Any], trigger: dict[str, Any]) -> list[str]:
    prompt_parts = [str(trigger.get("prompt") or ""), str(trigger.get("issue_subject") or "")]
    if not any(part.strip() for part in prompt_parts):
        previous = dev_pipeline_artifact_json(DEV_PIPELINE_STUDIO_ROOT, "execution/execution_run.json")
        prompt_parts.extend([str(previous.get("prompt") or ""), str(previous.get("issue_subject") or "")])
    for item in template.get("required_inputs", []):
        if not isinstance(item, dict):
            continue
        label = f"{item.get('id') or ''} {item.get('title') or ''} {item.get('detail') or ''}".lower()
        if not any(token in label for token in ("target", "write", "owned", "change blueprint", "expected target", "allowed change")):
            continue
        prompt_parts.extend(
            [
                str(item.get("answer") or ""),
                " ".join(str(value) for value in item.get("answer_values", []) if isinstance(value, str)),
                " ".join(str(value) for value in item.get("paths", []) if isinstance(value, str)),
            ]
        )
    paths = dev_pipeline_extract_target_paths_from_text("\n".join(part for part in prompt_parts if part))
    paths = [
        path
        for path in paths
        if not any(other != path and other.endswith(f"/{path}") for other in paths)
    ]
    return paths[:8]


def dev_pipeline_template_is_parallel_workset(template: dict[str, Any]) -> bool:
    return str(template.get("id") or "") == PARALLEL_PIPELINE_TEMPLATE_ID


def dev_pipeline_template_is_patch_swarm(template: dict[str, Any]) -> bool:
    return str(template.get("id") or "") == PATCH_SWARM_TEMPLATE_ID


def dev_pipeline_int_value(value: Any, default: int, minimum: int = 1, maximum: int = 12) -> int:
    try:
        result = int(float(str(value).strip()))
    except (TypeError, ValueError):
        result = default
    return max(minimum, min(maximum, result))


def dev_pipeline_parallel_input_text(template: dict[str, Any], trigger: dict[str, Any]) -> str:
    parts = [str(trigger.get("prompt") or ""), str(trigger.get("issue_subject") or "")]
    for item in template.get("required_inputs", []):
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id") or "")
        if item_id not in {"parallel-objective", "parallel-workstreams", "parallel-ui-config"}:
            continue
        parts.extend(
            [
                str(item.get("answer") or ""),
                str(item.get("answer_notes") or ""),
                "\n".join(str(value) for value in item.get("answer_values", []) if isinstance(value, str)),
                "\n".join(str(value) for value in item.get("paths", []) if isinstance(value, str)),
            ]
        )
    return "\n".join(part for part in parts if part).strip()


def dev_pipeline_parallel_max_parallel(template: dict[str, Any], trigger: dict[str, Any]) -> int:
    text = dev_pipeline_parallel_input_text(template, trigger)
    match = re.search(r"\bmax[_ -]?parallel(?:ism)?\b\s*[:=]?\s*(\d+)", text, flags=re.IGNORECASE)
    if match:
        return dev_pipeline_int_value(match.group(1), dev_pipeline_int_value(template.get("max_parallel"), 4))
    match = re.search(r"\bparallel(?:ism)?\b\s*[:=]?\s*(\d+)", text, flags=re.IGNORECASE)
    if match:
        return dev_pipeline_int_value(match.group(1), dev_pipeline_int_value(template.get("max_parallel"), 4))
    return dev_pipeline_int_value(template.get("max_parallel"), 4)


def dev_pipeline_parallel_config_map(template: dict[str, Any], trigger: dict[str, Any]) -> dict[str, str]:
    text = dev_pipeline_parallel_input_text(template, trigger)
    config: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = re.sub(r"[^a-z0-9_]+", "_", key.strip().lower()).strip("_")
        value = value.strip()
        if key and value:
            config[key] = value
    return config


def dev_pipeline_parallel_float_config(config: dict[str, str], key: str, default: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    try:
        value = float(str(config.get(key, "")).strip())
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def dev_pipeline_parallel_runtime_config(template: dict[str, Any], trigger: dict[str, Any]) -> dict[str, Any]:
    config = dev_pipeline_parallel_config_map(template, trigger)
    runtime = str(config.get("runtime") or "fixture").strip().lower()
    runtime_aliases = {
        "fixture dry run": "fixture",
        "fixture-dry-run": "fixture",
        "dry-run": "fixture",
        "api workers": "api-openai",
        "api": "api-openai",
        "openai": "api-openai",
    }
    runtime = runtime_aliases.get(runtime, runtime)
    if runtime not in {"fixture", "api-openai", "local-command"}:
        runtime = "fixture"
    apply_mode = str(config.get("apply_mode") or config.get("apply") or "dry-run").strip().lower()
    apply_enabled = apply_mode in {"apply", "sequential", "yes", "true", "1"}
    max_parallel = dev_pipeline_parallel_max_parallel(template, trigger)
    default_budget = 0.0 if runtime == "fixture" else DEV_PIPELINE_DELIVERY_BUDGET_USD
    default_max_budget = 0.0 if runtime == "fixture" else DEV_PIPELINE_DELIVERY_MAX_BUDGET_USD
    return {
        "max_parallel": max_parallel,
        "runtime": runtime,
        "integrator": str(config.get("integrator") or "sequential").strip().lower() or "sequential",
        "validation": str(config.get("validation") or "smoke").strip().lower() or "smoke",
        "apply_mode": "apply" if apply_enabled else "dry-run",
        "apply_enabled": apply_enabled,
        "budget_usd": dev_pipeline_parallel_float_config(config, "budget_usd", default_budget),
        "max_budget_usd": dev_pipeline_parallel_float_config(config, "max_budget_usd", default_max_budget),
    }


def dev_pipeline_parallel_auto_target_paths(project: dict[str, Any], run_id: str, runtime_config: dict[str, Any]) -> list[str]:
    max_parallel = dev_pipeline_int_value(runtime_config.get("max_parallel"), 10)
    if str(runtime_config.get("runtime") or "") == "fixture":
        return PARALLEL_PIPELINE_FIXTURE_TARGET_PATHS[:max_parallel]
    owned_root = str(project.get("owned_root") or "workspace/runs/parallel-pipeline/outputs").strip().strip("/")
    return [f"{owned_root}/{run_id}/worker-{index:02d}.md" for index in range(1, max_parallel + 1)]


def dev_pipeline_parallel_task_from_mapping(item: dict[str, Any], index: int, read_paths: list[str], prompt: str) -> dict[str, Any] | None:
    write_paths = dev_pipeline_text_list(item.get("write_paths") or item.get("paths") or item.get("owned_paths"), [])
    write_paths = [dev_pipeline_clean_target_path(path) for path in write_paths]
    write_paths = [path for path in write_paths if path]
    if not write_paths:
        return None
    task_id = dev_pipeline_workset_slug(str(item.get("id") or item.get("task_id") or f"parallel-{index}"))
    task_title = str(item.get("task") or item.get("title") or f"Parallel workstream {index}").strip()
    description = str(item.get("description") or "").strip()
    if not description:
        description = (
            "Implement this independent parallel workstream using only its exclusive write paths. "
            "Return complete UTF-8 contents for every changed owned path using patch_proposal.v1. "
            "Do not edit files outside write_paths. "
            f"\n\nOverall prompt:\n{prompt}"
        )
    return {
        "id": task_id,
        "worker_id": str(item.get("worker_id") or f"api-parallel-worker-{index}"),
        "task": task_title[:240],
        "description": description,
        "write_paths": write_paths,
        "read_paths": dev_pipeline_text_list(item.get("read_paths"), read_paths),
        "routes": dev_pipeline_text_list(item.get("routes"), []),
        "depends_on": dev_pipeline_text_list(item.get("depends_on") or item.get("dependencies"), []),
        "api_profile": str(item.get("api_profile") or DEV_PIPELINE_DELIVERY_API_PROFILE),
        "output_schema": str(item.get("output_schema") or DEV_PIPELINE_DELIVERY_OUTPUT_SCHEMA),
        "cost_usd_estimate": float(item.get("cost_usd_estimate") or 0.20),
    }


def dev_pipeline_parallel_tasks_from_json(text: str, read_paths: list[str], prompt: str) -> list[dict[str, Any]]:
    stripped = text.strip()
    if not stripped or stripped[0] not in "[{":
        return []
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return []
    if isinstance(payload, dict):
        raw_items = payload.get("tasks") or payload.get("workstreams") or payload.get("parallel_workstreams") or []
    else:
        raw_items = payload
    if not isinstance(raw_items, list):
        return []
    tasks = []
    for index, item in enumerate(raw_items, start=1):
        if not isinstance(item, dict):
            continue
        task = dev_pipeline_parallel_task_from_mapping(item, index, read_paths, prompt)
        if task:
            tasks.append(task)
    return tasks


def dev_pipeline_parallel_task_specs(
    project: dict[str, Any],
    template: dict[str, Any],
    trigger: dict[str, Any],
    target_paths: list[str],
    prompt: str,
) -> list[dict[str, Any]]:
    read_paths = [str(value) for value in project.get("read_paths", []) if isinstance(value, str) and value.strip()]
    text = dev_pipeline_parallel_input_text(template, trigger)
    tasks = dev_pipeline_parallel_tasks_from_json(text, read_paths, prompt)
    if tasks:
        return tasks
    result = []
    for index, path in enumerate(target_paths, start=1):
        result.append(
            {
                "id": dev_pipeline_workset_slug(f"parallel-{index}-{Path(path).stem}") or f"parallel-{index}",
                "worker_id": f"api-parallel-worker-{index}",
                "task": f"Implement exclusive workstream for {path}"[:240],
                "description": (
                    "Implement this independent parallel workstream using only its exclusive write path. "
                    "Return complete UTF-8 contents for every changed owned path using patch_proposal.v1. "
                    "Do not edit files outside write_paths. "
                    f"Exclusive write path: {path}\n\nOverall prompt:\n{prompt}"
                ),
                "write_paths": [path],
                "read_paths": read_paths,
                "routes": [],
                "depends_on": [],
                "api_profile": DEV_PIPELINE_DELIVERY_API_PROFILE,
                "output_schema": DEV_PIPELINE_DELIVERY_OUTPUT_SCHEMA,
                "cost_usd_estimate": 0.20,
            }
        )
    return result


def dev_pipeline_dirty_target_errors(paths: list[str]) -> list[str]:
    if not paths:
        return []
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain", "--", *paths],
            cwd=ROOT_DIR,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except FileNotFoundError:
        return ["git is unavailable; dirty target-path checks cannot run"]
    if proc.returncode != 0:
        return [proc.stderr.strip() or "git status failed for target paths"]
    dirty = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    if not dirty:
        return []
    errors: list[str] = []
    for line in dirty:
        status = line[:2].strip() or "modified"
        path = line[3:].strip() if len(line) > 3 else line
        reason = "untracked" if "?" in status else "modified"
        errors.append(
            f"Target path is already {reason}: {path}. Use a fresh target path or commit/remove the existing file before rerunning."
        )
    return errors


def dev_pipeline_delivery_workset(
    root: Path,
    project: dict[str, Any],
    template: dict[str, Any],
    trigger: dict[str, Any],
    run_id: str,
    target_paths: list[str],
    budget_usd: float,
    max_budget_usd: float,
    runtime_config: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    prompt = dev_pipeline_delivery_prompt(project, template, trigger)
    issue_id = str(trigger.get("issue_id") or "").strip()
    subject = str(trigger.get("issue_subject") or "").strip()
    prompt_lines = prompt.splitlines()
    task_text = subject or (prompt_lines[0] if prompt_lines else "Implement requested repo change")
    read_paths = [str(value) for value in project.get("read_paths", []) if isinstance(value, str) and value.strip()]
    workset_id = dev_pipeline_slug(f"delivery-{template.get('id')}-{project.get('id')}-{run_id}", "delivery")
    is_parallel = dev_pipeline_template_is_parallel_workset(template)
    runtime_config = runtime_config if isinstance(runtime_config, dict) else {}
    max_parallel = dev_pipeline_int_value(runtime_config.get("max_parallel"), dev_pipeline_parallel_max_parallel(template, trigger)) if is_parallel else 1
    if is_parallel:
        tasks = dev_pipeline_parallel_task_specs(project, template, trigger, target_paths, prompt)
        if str(runtime_config.get("runtime") or "") == "fixture":
            for index, task in enumerate(tasks, start=1):
                if isinstance(task, dict) and str(task.get("worker_id") or "").startswith("api-parallel-worker"):
                    task["worker_id"] = f"fixture-parallel-worker-{index}"
    else:
        description = (
            "Implement the requested bounded repo change using only the declared write paths. "
            "Return complete UTF-8 contents for every changed owned path using patch_proposal.v1. "
            "Do not edit files outside write_paths. Keep the change minimal and runnable. "
            f"Budget target: ${budget_usd:.2f}; hard cap: ${max_budget_usd:.2f}. "
            f"Issue: {issue_id or 'manual'}.\n\nPrompt:\n{prompt}"
        )
        tasks = [
            {
                "id": "delivery",
                "worker_id": "api-delivery-worker",
                "task": task_text[:240],
                "description": description,
                "write_paths": target_paths,
                "read_paths": read_paths,
                "routes": [],
                "depends_on": [],
                "api_profile": DEV_PIPELINE_DELIVERY_API_PROFILE,
                "output_schema": DEV_PIPELINE_DELIVERY_OUTPUT_SCHEMA,
                "cost_usd_estimate": 0.20,
            }
        ]
    workset = {
        "schema_version": "cento.workset.v1",
        "id": workset_id,
        "mode": "fast",
        "max_parallel": max_parallel,
        "read_paths": read_paths,
        "execution_model": "parallel" if is_parallel else "single",
        "integration": "sequential",
        "runtime": str(runtime_config.get("runtime") or "api-openai"),
        "apply_mode": str(runtime_config.get("apply_mode") or "apply"),
        "validation": str(runtime_config.get("validation") or "smoke"),
        "integration_model_policy": {
            "mode": "deterministic-first",
            "integrator": str(runtime_config.get("integrator") or "sequential"),
            "fallback": "only-if-needed",
            "model_ceiling": DEV_PIPELINE_INTEGRATION_MODEL_CEILING,
            "profile": "api-mini-integrator",
        },
        "issue_id": issue_id,
        "tasks": tasks,
    }
    rel_path = f"execution/worksets/{run_id}.json"
    workset_path = dev_pipeline_root_path(root, rel_path)
    write_json_path(workset_path, workset)
    return dev_pipeline_relative(workset_path), workset


def dev_pipeline_delivery_readiness(target_paths: list[str], workset_rel: str, runtime_config: dict[str, Any] | None = None) -> tuple[list[str], dict[str, Any]]:
    runtime_config = runtime_config if isinstance(runtime_config, dict) else {}
    runtime = str(runtime_config.get("runtime") or "api-openai")
    apply_enabled = bool(runtime_config.get("apply_enabled", True))
    config, config_errors = dev_pipeline_api_worker_config() if runtime == "api-openai" else ({}, [])
    errors: list[str] = []
    if not target_paths:
        errors.append("No explicit repo-relative write path was found in the prompt or input contract")
    if not workset_rel and target_paths:
        errors.append("Workset manifest was not written")
    errors.extend(config_errors)
    if apply_enabled:
        errors.extend(dev_pipeline_dirty_target_errors(target_paths))
    openai_config = config.get("openai") if isinstance(config.get("openai"), dict) else {}
    profiles = config.get("profiles") if isinstance(config.get("profiles"), dict) else {}
    profile = profiles.get(DEV_PIPELINE_DELIVERY_API_PROFILE) if isinstance(profiles.get(DEV_PIPELINE_DELIVERY_API_PROFILE), dict) else {}
    return errors, {
        "runtime": runtime,
        "api_profile": DEV_PIPELINE_DELIVERY_API_PROFILE,
        "model": dev_pipeline_env_reference(str(profile.get("model") or "")),
        "budget_usd": runtime_config.get("budget_usd", DEV_PIPELINE_DELIVERY_BUDGET_USD),
        "max_budget_usd": runtime_config.get("max_budget_usd", DEV_PIPELINE_DELIVERY_MAX_BUDGET_USD),
        "apply_mode": runtime_config.get("apply_mode", "apply"),
        "configured_budget_max_usd": openai_config.get("budget_usd_max"),
    }


def dev_pipeline_delivery_seed_steps(workset_rel: str, status: str, input_ready: bool = True, workset: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    base_status = "completed" if input_ready else "blocked"
    workset = workset if isinstance(workset, dict) else {}
    tasks = [item for item in workset.get("tasks", []) if isinstance(item, dict)]
    is_parallel = int(workset.get("max_parallel") or 1) > 1 or len(tasks) > 1
    if is_parallel:
        queued_or_blocked = "queued" if status == "running" else "blocked"
        return [
            {"id": "resolve-parallel-inputs", "title": "Resolve contract and exclusive write paths", "status": base_status, "duration": "0s", "duration_seconds": 0, "file": "execution/execution_run.json"},
            {"id": "write-parallel-workset", "title": "Write parallel workset manifest", "status": "completed" if workset_rel else "blocked", "duration": "0s", "duration_seconds": 0, "file": workset_rel},
            *[
                {
                    "id": f"parallel-worker-{str(task.get('id') or index)}",
                    "title": f"Worker: {str(task.get('task') or task.get('id') or f'parallel {index}')}",
                    "status": queued_or_blocked,
                    "duration": "0s",
                    "duration_seconds": 0,
                    "file": ", ".join(str(path) for path in task.get("write_paths", []) if isinstance(path, str)),
                    "stage": "execution",
                }
                for index, task in enumerate(tasks, start=1)
            ],
            {"id": "collect-worker-artifacts", "title": "Collect worker artifacts", "status": queued_or_blocked, "duration": "0s", "duration_seconds": 0, "file": ""},
            {"id": "integrate-sequentially", "title": "Integrate patches sequentially", "status": queued_or_blocked, "duration": "0s", "duration_seconds": 0, "file": ""},
            {"id": "run-parallel-validation", "title": "Run parallel validation gates", "status": queued_or_blocked, "duration": "0s", "duration_seconds": 0, "file": ""},
            {"id": "collect-parallel-evidence", "title": "Collect receipts, cost, and evidence", "status": queued_or_blocked, "duration": "0s", "duration_seconds": 0, "file": ""},
        ]
    return [
        {"id": "resolve-prompt", "title": "Resolve prompt and target paths", "status": base_status, "duration": "0s", "duration_seconds": 0, "file": "execution/execution_run.json"},
        {"id": "write-workset", "title": "Write executable workset", "status": "completed" if workset_rel else "blocked", "duration": "0s", "duration_seconds": 0, "file": workset_rel},
        {"id": "api-worker", "title": "OpenAI patch proposal worker", "status": "queued" if status == "running" else "blocked", "duration": "0s", "duration_seconds": 0, "file": ""},
        {"id": "materialize-patch", "title": "Materialize patch bundle", "status": "queued" if status == "running" else "blocked", "duration": "0s", "duration_seconds": 0, "file": ""},
        {"id": "integrate-sequential", "title": "Integrate patch sequentially", "status": "queued" if status == "running" else "blocked", "duration": "0s", "duration_seconds": 0, "file": ""},
        {"id": "apply-worktree", "title": "Apply accepted change to worktree", "status": "queued" if status == "running" else "blocked", "duration": "0s", "duration_seconds": 0, "file": ""},
        {"id": "collect-receipts", "title": "Collect receipts, cost, and evidence", "status": "queued" if status == "running" else "blocked", "duration": "0s", "duration_seconds": 0, "file": ""},
    ]


def dev_pipeline_delivery_stage_payloads(started: datetime, status: str, finished: datetime | None = None, input_ready: bool = True) -> list[dict[str, Any]]:
    final = finished or started
    is_blocked = status == "blocked"
    intake_status = "completed" if input_ready else "blocked"
    return [
        {"id": "input", "started_at": started.isoformat(), "finished_at": final.isoformat(), "status": intake_status},
        {"id": "repo", "started_at": started.isoformat(), "finished_at": final.isoformat(), "status": intake_status},
        {"id": "blueprint", "started_at": started.isoformat(), "finished_at": final.isoformat(), "status": intake_status},
        {"id": "factory", "started_at": started.isoformat(), "finished_at": final.isoformat() if finished else "", "status": status},
        {"id": "validation", "started_at": final.isoformat() if finished else "", "finished_at": final.isoformat() if finished else "", "status": "completed" if status == "completed" else ("blocked" if is_blocked else "queued")},
        {"id": "handoff", "started_at": final.isoformat() if finished else "", "finished_at": final.isoformat() if finished else "", "status": "completed" if status == "completed" else ("blocked" if is_blocked else "queued")},
    ]


def dev_pipeline_hard_proreq_artifacts(run_id: str) -> list[dict[str, Any]]:
    rels = [
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/{run_id}/operator_intake.json",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/{run_id}/mini_cento_context.json",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/{run_id}/ui_screenshot_request.json",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/{run_id}/existing_ui_reference.png",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/{run_id}/existing_ui_reference_square.png",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/{run_id}/image_generation_request.json",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/{run_id}/image_generation_response.json",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/{run_id}/generated_integrator_screenshot.png",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/{run_id}/pro_output_schema.json",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/{run_id}/pro_backend_request.json",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/{run_id}/proreq_light_codex_prompt.md",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/{run_id}/proreq_light_output_schema.json",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/{run_id}/proreq_light_codex_command.json",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/{run_id}/proreq_light_codex_stdout.txt",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/{run_id}/proreq_light_codex_stderr.txt",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/{run_id}/proreq_light_codex_response.json",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/{run_id}/pro_backend_response.json",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/{run_id}/pro_backend_error.json",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/{run_id}/pro_backend_plan.json",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/{run_id}/story_index.json",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/{run_id}/parallel_patch_workset.json",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/{run_id}/manifest_integration_policy.json",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/{run_id}/backend_work_manifest.json",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/{run_id}/integration_plan.json",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/{run_id}/validation_plan.json",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/{run_id}/closed_loop_check_stdout.txt",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/{run_id}/closed_loop_check_stderr.txt",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/{run_id}/closed_loop_workset_stdout.txt",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/{run_id}/closed_loop_workset_stderr.txt",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/{run_id}/closed_loop_delivery.json",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/{run_id}/closed_loop_validation.json",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/{run_id}/closed_loop_evidence.json",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/{run_id}/closed_loop_evidence.md",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/{run_id}/closed_loop_incident.json",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/{run_id}/closed_loop_incident.md",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/delivery/{run_id}/closed-loop.stdout.log",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/delivery/{run_id}/closed-loop.stderr.log",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/{run_id}/hard_proreq_evidence.json",
    ]
    return [
        {
            "name": Path(rel).name,
            "path": rel,
            "exists": (ROOT_DIR / rel).exists(),
            "size": file_size_label(ROOT_DIR / rel),
        }
        for rel in rels
    ]


def dev_pipeline_hard_proreq_stage_payloads(started: datetime, status: str, finished: datetime | None = None) -> list[dict[str, Any]]:
    final = finished or started
    return [
        {"id": "input", "started_at": started.isoformat(), "finished_at": final.isoformat() if finished else "", "status": "completed" if finished else "running"},
        {"id": "repo", "started_at": started.isoformat(), "finished_at": final.isoformat() if finished else "", "status": "completed" if finished else "queued"},
        {"id": "blueprint", "started_at": started.isoformat(), "finished_at": final.isoformat() if finished else "", "status": "completed" if finished else "queued"},
        {"id": "factory", "started_at": started.isoformat(), "finished_at": final.isoformat() if finished else "", "status": status},
        {"id": "validation", "started_at": final.isoformat() if finished else "", "finished_at": final.isoformat() if finished else "", "status": "completed" if status == "completed" else ("blocked" if status == "blocked" else "queued")},
        {"id": "handoff", "started_at": final.isoformat() if finished else "", "finished_at": final.isoformat() if finished else "", "status": "completed" if status == "completed" else ("blocked" if status == "blocked" else "queued")},
    ]


def dev_pipeline_multipipeline_artifacts(run_id: str) -> list[dict[str, Any]]:
    rels = [
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/multipipeline/{run_id}/operator_intake.json",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/multipipeline/{run_id}/multipipeline_schedule.json",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/multipipeline/{run_id}/pass_01_proreq_request.json",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/multipipeline/{run_id}/pass_01_guidance.json",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/multipipeline/{run_id}/pass_02_proreq_request.json",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/multipipeline/{run_id}/pass_02_guidance.json",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/multipipeline/{run_id}/pass_03_proreq_request.json",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/multipipeline/{run_id}/pass_03_guidance.json",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/multipipeline/{run_id}/pass_04_proreq_request.json",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/multipipeline/{run_id}/pass_04_guidance.json",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/multipipeline/{run_id}/ui_screenshot_request.json",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/multipipeline/{run_id}/chatgpt_pro_request.json",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/multipipeline/{run_id}/chain_roadmap.md",
        f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/multipipeline/{run_id}/multipipeline_evidence.json",
    ]
    return [
        {
            "name": Path(rel).name,
            "path": rel,
            "exists": (ROOT_DIR / rel).exists(),
            "size": file_size_label(ROOT_DIR / rel),
        }
        for rel in rels
    ]


def dev_pipeline_multipipeline_stage_payloads(started: datetime, status: str, finished: datetime | None = None) -> list[dict[str, Any]]:
    final = finished or started
    return [
        {"id": "input", "started_at": started.isoformat(), "finished_at": final.isoformat() if finished else "", "status": "completed" if finished else "running"},
        {"id": "repo", "started_at": started.isoformat(), "finished_at": final.isoformat() if finished else "", "status": "completed" if finished else "queued"},
        {"id": "blueprint", "started_at": started.isoformat(), "finished_at": final.isoformat() if finished else "", "status": "completed" if finished else "queued"},
        {"id": "factory", "started_at": started.isoformat(), "finished_at": final.isoformat() if finished else "", "status": status},
        {"id": "validation", "started_at": final.isoformat() if finished else "", "finished_at": final.isoformat() if finished else "", "status": "completed" if status == "completed" else ("blocked" if status == "blocked" else "queued")},
        {"id": "handoff", "started_at": final.isoformat() if finished else "", "finished_at": final.isoformat() if finished else "", "status": "completed" if status == "completed" else ("blocked" if status == "blocked" else "queued")},
    ]


def dev_pipeline_patch_swarm_artifacts(run_id: str) -> list[dict[str, Any]]:
    base = f"workspace/runs/parallel-delivery/patch-swarm/{run_id}"
    rels = [
        f"{base}/patch_swarm_manifest.json",
        f"{base}/proreq_execution_manifest.json",
        f"{base}/candidate_index.json",
        f"{base}/dedupe_clusters.json",
        f"{base}/ranking.json",
        f"{base}/cost_ledger.json",
        f"{base}/patch_swarm_receipt.json",
        f"{base}/integration_execution/integration_execution.json",
        f"{base}/safe_integrator_handoff.json",
        f"{base}/validation_summary.json",
        f"{base}/ui_state.json",
        f"{base}/decision_report.md",
        "workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/patch-swarm/latest_ui_state.json",
    ]
    return [
        {
            "name": Path(rel).name,
            "path": rel,
            "exists": (ROOT_DIR / rel).exists(),
            "size": file_size_label(ROOT_DIR / rel),
        }
        for rel in rels
    ]


def dev_pipeline_patch_swarm_stage_payloads(started: datetime, status: str, finished: datetime | None = None) -> list[dict[str, Any]]:
    final = finished or started
    return [
        {"id": "input", "started_at": started.isoformat(), "finished_at": final.isoformat() if finished else "", "status": "completed" if finished else "running"},
        {"id": "repo", "started_at": started.isoformat(), "finished_at": final.isoformat() if finished else "", "status": "completed" if finished else "queued"},
        {"id": "blueprint", "started_at": started.isoformat(), "finished_at": final.isoformat() if finished else "", "status": "completed" if finished else "queued"},
        {"id": "factory", "started_at": started.isoformat(), "finished_at": final.isoformat() if finished else "", "status": status},
        {"id": "validation", "started_at": final.isoformat() if finished else "", "finished_at": final.isoformat() if finished else "", "status": "completed" if status == "completed" else ("blocked" if status == "blocked" else "queued")},
        {"id": "handoff", "started_at": final.isoformat() if finished else "", "finished_at": final.isoformat() if finished else "", "status": "completed" if status == "completed" else ("blocked" if status == "blocked" else "queued")},
    ]


def dev_pipeline_patch_swarm_config(template: dict[str, Any], trigger: dict[str, Any]) -> dict[str, Any]:
    parts = [str(trigger.get("prompt") or ""), str(trigger.get("issue_subject") or "")]
    for item in template.get("required_inputs", []):
        if not isinstance(item, dict):
            continue
        if str(item.get("id") or "") not in {"patch-swarm-objective", "patch-swarm-provider-policy"}:
            continue
        parts.extend([str(item.get("answer") or ""), str(item.get("answer_notes") or "")])
        parts.extend(str(value) for value in item.get("answer_values", []) if isinstance(value, str))
    text = "\n".join(part for part in parts if part)
    config: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = re.sub(r"[^a-z0-9_]+", "_", key.strip().lower()).strip("_")
        value = value.strip()
        if key and value:
            config[key] = value
    return {
        "candidate_target": dev_pipeline_int_value(config.get("candidate_target"), 100, minimum=100, maximum=500),
        "max_parallel_agents": dev_pipeline_int_value(config.get("max_parallel_agents"), 5, minimum=1, maximum=20),
        "providers": config.get("providers") or "codex-exec,claude-code,api-openai",
        "live": str(config.get("mode") or "fixture").lower() in {"live", "real"},
    }


def dev_pipeline_seed_patch_swarm_execution(
    root: Path,
    manifest: dict[str, Any],
    project: dict[str, Any],
    template: dict[str, Any],
    trigger: dict[str, Any],
) -> dict[str, Any]:
    execution_manifest_rel = str(template.get("execution_manifest") or "execution/patch_swarm_execution_manifest.json")
    execution_manifest = {}
    execution_steps = dev_pipeline_template_factory_steps(template)
    if not execution_steps:
        raise AgentWorkAppError("No Patch Swarm execution steps are configured")
    run_started = datetime.now(timezone.utc)
    run_id = f"patch-swarm-ui-{run_started.strftime('%Y%m%dT%H%M%S%fZ')}"
    prompt = dev_pipeline_delivery_prompt(project, template, trigger)
    config = dev_pipeline_patch_swarm_config(template, trigger)
    inputs = dev_pipeline_template_required_inputs(template)
    for item in inputs:
        if str(item.get("id") or "") == "patch-swarm-objective" and prompt:
            item["status"] = "provided"
            item["answer"] = prompt
            item["answer_notes"] = "Captured from Run Pipeline prompt or structured Patch Swarm answers."
            item["provided_at"] = run_started.isoformat()
    template["required_inputs"] = dev_pipeline_write_input_manifests(root, manifest, project, template, inputs)
    queued_steps = [
        {
            **step,
            "id": str(step.get("id") or f"step-{index}"),
            "title": str(step.get("title") or step.get("id") or f"step-{index}"),
            "status": "queued",
            "exit_code": None,
            "duration": "0s",
            "duration_seconds": 0,
            "started_at": "",
            "finished_at": "",
            "stdout_tail": "",
            "stderr_tail": "",
        }
        for index, step in enumerate(execution_steps, start=1)
    ]
    run_payload = {
        "schema_version": "cento.execution_run.v1",
        "source": "cento-patch-swarm",
        "run_id": run_id,
        "pipeline": f"{template.get('id') or 'pipeline'}-{project.get('id') or 'project'}",
        "status": "running",
        "started_at": run_started.isoformat(),
        "finished_at": "",
        "duration_seconds": 0,
        "triggered_by": str(trigger.get("triggered_by") or "pipeline-run-api"),
        "issue_id": str(trigger.get("issue_id") or ""),
        "issue_subject": str(trigger.get("issue_subject") or ""),
        "prompt": prompt,
        "inputs": inputs,
        "runtime": "cento parallel-delivery patch-swarm e2e fixture; provider adapters codex-exec, claude-code, api-openai",
        "apply_mode": "safe-integrator-handoff-only",
        "candidate_target": config["candidate_target"],
        "max_parallel_agents": config["max_parallel_agents"],
        "providers": config["providers"],
        "budget_usd": 0.0,
        "max_budget_usd": 20.0,
        "stages": dev_pipeline_patch_swarm_stage_payloads(run_started, "running"),
        "steps": queued_steps,
        "logs": [
            {
                "timestamp": run_started.isoformat(),
                "stage": "pipeline",
                "source": "patch-swarm",
                "message": f"Patch Swarm started: {config['candidate_target']} candidates across ten ProReq lanes and one dedicated integrator",
            }
        ],
        "artifacts": dev_pipeline_patch_swarm_artifacts(run_id),
        "facts": [
            {"label": "Engine", "value": "cento parallel-delivery patch-swarm"},
            {"label": "Providers", "value": config["providers"]},
            {"label": "Candidates", "value": str(config["candidate_target"])},
            {"label": "Max agents", "value": str(config["max_parallel_agents"])},
            {"label": "Integrator", "value": "one dedicated serialized Safe Integrator handoff"},
            {"label": "Budget", "value": "$0.00 fixture path / live API opt-in"},
        ],
        "written_at": datetime.now(timezone.utc).isoformat(),
    }
    dev_pipeline_write_execution_state(root, execution_manifest_rel, execution_manifest, run_payload)
    return run_payload


def dev_pipeline_seed_hard_proreq_execution(
    root: Path,
    manifest: dict[str, Any],
    project: dict[str, Any],
    template: dict[str, Any],
    trigger: dict[str, Any],
) -> dict[str, Any]:
    execution_manifest_rel = str(template.get("execution_manifest") or "execution/execution_manifest.json")
    execution_manifest = {}
    execution_steps = dev_pipeline_template_factory_steps(template)
    if not execution_steps:
        raise AgentWorkAppError("No hard proreq execution steps are configured")
    run_started = datetime.now(timezone.utc)
    run_id = f"{template.get('id') or 'pipeline'}-{project.get('id') or 'project'}-{run_started.strftime('%Y%m%dT%H%M%S%fZ')}"
    prompt = dev_pipeline_delivery_prompt(project, template, trigger)
    is_light = str(template.get("id") or "") == PROREQ_LIGHT_TEMPLATE_ID
    requested_delivery_mode = str(trigger.get("delivery_mode") or "").strip()
    delivery_mode = requested_delivery_mode if requested_delivery_mode else ("closed-loop" if is_light else "plan-only")
    inputs = dev_pipeline_template_required_inputs(template)
    for item in inputs:
        if str(item.get("id") or "") == "operator-thoughts" and prompt:
            item["status"] = "provided"
            item["answer"] = prompt
            item["answer_notes"] = "Captured from Run Pipeline prompt or manual rerun context."
            item["provided_at"] = run_started.isoformat()
    template["required_inputs"] = dev_pipeline_write_input_manifests(root, manifest, project, template, inputs)
    queued_steps: list[dict[str, Any]] = []
    for index, step in enumerate(execution_steps, start=1):
        step_id = str(step.get("id") or f"step-{index}")
        command = dev_pipeline_execution_command_for_step(step_id)
        queued_steps.append(
            {
                **step,
                "id": step_id,
                "title": str(step.get("title") or step_id),
                "status": "queued",
                "command": shlex.join(command),
                "exit_code": None,
                "duration": "0s",
                "duration_seconds": 0,
                "started_at": "",
                "finished_at": "",
                "stdout_tail": "",
                "stderr_tail": "",
            }
        )
    run_payload = {
        "schema_version": "cento.execution_run.v1",
        "source": "cento-proreq-light-codex" if is_light else "cento-hard-proreq-pro",
        "run_id": run_id,
        "pipeline": f"{template.get('id') or 'pipeline'}-{project.get('id') or 'project'}",
        "status": "running",
        "started_at": run_started.isoformat(),
        "finished_at": "",
        "duration_seconds": 0,
        "triggered_by": str(trigger.get("triggered_by") or "prompt-router"),
        "issue_id": str(trigger.get("issue_id") or ""),
        "issue_subject": str(trigger.get("issue_subject") or ""),
        "prompt": prompt,
        "inputs": inputs,
        "runtime": (
            "cento-native + Codex Exec ProReq-light + 10-story split + closed-loop Codex patch delivery"
            if is_light
            else f"cento-native + 10-story split + integration model ceiling {DEV_PIPELINE_INTEGRATION_MODEL_CEILING}"
        ),
        "delivery_mode": delivery_mode,
        "apply_mode": "closed-loop-clean-apply" if is_light and delivery_mode == "closed-loop" else "backend-plan-first",
        "budget_usd": DEV_PIPELINE_DELIVERY_BUDGET_USD,
        "max_budget_usd": DEV_PIPELINE_DELIVERY_MAX_BUDGET_USD,
        "stages": dev_pipeline_hard_proreq_stage_payloads(run_started, "running"),
        "steps": queued_steps,
        "logs": [
            {
                "timestamp": run_started.isoformat(),
                "stage": "pipeline",
                "source": "proreq-light" if is_light else "hard-proreq",
                "message": (
                    f"ProReq-light run started; Codex Exec will simulate the ChatGPT Pro planning lane and delivery_mode={delivery_mode}"
                    if is_light
                    else "Hard proreq run started; GPT pro backend planning request will use strict JSON Schema and frontend screenshot flow stays muted"
                ),
            }
        ],
        "artifacts": dev_pipeline_hard_proreq_artifacts(run_id),
        "facts": [
            {"label": "Engine", "value": "cento proreq light" if is_light else "cento hard proreq"},
            {"label": "Runtime", "value": "codex exec as ChatGPT Pro simulator + local Codex workers" if is_light else "cento-native + ten story manifests"},
            {"label": "Delivery", "value": delivery_mode if is_light else "plan-only"},
            {"label": "Model ceiling", "value": f"integration fallback at most {DEV_PIPELINE_INTEGRATION_MODEL_CEILING}"},
            {"label": "Schema", "value": "codex exec --output-schema with hard proreq JSON schema" if is_light else "strict Responses JSON Schema + codex --output-schema"},
            {"label": "Frontend lane", "value": "muted separate screenshot flow"},
            {"label": "Budget", "value": "$0.00 metered OpenAI API / Codex Exec route" if is_light else f"${DEV_PIPELINE_DELIVERY_BUDGET_USD:.2f} target / ${DEV_PIPELINE_DELIVERY_MAX_BUDGET_USD:.2f} cap"},
        ],
        "written_at": datetime.now(timezone.utc).isoformat(),
    }
    dev_pipeline_write_execution_state(root, execution_manifest_rel, execution_manifest, run_payload)
    return run_payload


def dev_pipeline_seed_multipipeline_execution(
    root: Path,
    manifest: dict[str, Any],
    project: dict[str, Any],
    template: dict[str, Any],
    trigger: dict[str, Any],
) -> dict[str, Any]:
    execution_manifest_rel = str(template.get("execution_manifest") or "execution/multipipeline_execution_manifest.json")
    execution_manifest = {}
    execution_steps = dev_pipeline_template_factory_steps(template)
    if not execution_steps:
        raise AgentWorkAppError("No multipipeline ProReq execution steps are configured")
    run_started = datetime.now(timezone.utc)
    run_id = f"{template.get('id') or 'pipeline'}-{project.get('id') or 'project'}-{run_started.strftime('%Y%m%dT%H%M%S%fZ')}"
    prompt = dev_pipeline_delivery_prompt(project, template, trigger)
    inputs = dev_pipeline_template_required_inputs(template)
    for item in inputs:
        if str(item.get("id") or "") == "multipipeline-objective" and prompt:
            item["status"] = "provided"
            item["answer"] = prompt
            item["answer_notes"] = "Captured from Run Pipeline prompt or structured objective answers."
            item["provided_at"] = run_started.isoformat()
    template["required_inputs"] = dev_pipeline_write_input_manifests(root, manifest, project, template, inputs)
    queued_steps: list[dict[str, Any]] = []
    for index, step in enumerate(execution_steps, start=1):
        step_id = str(step.get("id") or f"step-{index}")
        command = dev_pipeline_execution_command_for_step(step_id)
        queued_steps.append(
            {
                **step,
                "id": step_id,
                "title": str(step.get("title") or step_id),
                "status": "queued",
                "command": shlex.join(command),
                "exit_code": None,
                "duration": "0s",
                "duration_seconds": 0,
                "started_at": "",
                "finished_at": "",
                "stdout_tail": "",
                "stderr_tail": "",
            }
        )
    run_payload = {
        "schema_version": "cento.execution_run.v1",
        "source": "cento-multipipeline-proreq-chain",
        "run_id": run_id,
        "pipeline": f"{template.get('id') or 'pipeline'}-{project.get('id') or 'project'}",
        "status": "running",
        "started_at": run_started.isoformat(),
        "finished_at": "",
        "duration_seconds": 0,
        "triggered_by": str(trigger.get("triggered_by") or "pipeline-run-api"),
        "issue_id": str(trigger.get("issue_id") or ""),
        "issue_subject": str(trigger.get("issue_subject") or ""),
        "prompt": prompt,
        "inputs": inputs,
        "runtime": "cento-native + four sequential ProReq request passes + request-only Pro/image lanes",
        "apply_mode": "request-artifacts-only",
        "budget_usd": 0.0,
        "max_budget_usd": 0.0,
        "stages": dev_pipeline_multipipeline_stage_payloads(run_started, "running"),
        "steps": queued_steps,
        "logs": [
            {
                "timestamp": run_started.isoformat(),
                "stage": "pipeline",
                "source": "multipipeline-proreq",
                "message": "Multipipeline ProReq chain started; four ordered ProReq request passes will feed guidance forward without live Pro/image dispatch by default",
            }
        ],
        "artifacts": dev_pipeline_multipipeline_artifacts(run_id),
        "facts": [
            {"label": "Engine", "value": "cento multipipeline proreq"},
            {"label": "Runtime", "value": "4 sequential hard-proreq request passes"},
            {"label": "Model policy", "value": "request artifacts only unless live Pro/image is explicitly enabled"},
            {"label": "Schema", "value": "cento.multipipeline_proreq_chain.v1 + pipeline_run_request.v1"},
            {"label": "Frontend lane", "value": "muted UI screenshot request artifact"},
            {"label": "Budget", "value": "$0.00 deterministic / live calls opt-in"},
        ],
        "written_at": datetime.now(timezone.utc).isoformat(),
    }
    dev_pipeline_write_execution_state(root, execution_manifest_rel, execution_manifest, run_payload)
    return run_payload


def dev_pipeline_seed_execution_e2e(
    root: Path,
    manifest: dict[str, Any],
    project: dict[str, Any],
    template: dict[str, Any],
    trigger: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if str(template.get("id") or "") in {HARD_PROREQ_TEMPLATE_ID, PROREQ_LIGHT_TEMPLATE_ID}:
        return dev_pipeline_seed_hard_proreq_execution(root, manifest, project, template, trigger if isinstance(trigger, dict) else {})
    if str(template.get("id") or "") == MULTIPIPELINE_TEMPLATE_ID:
        return dev_pipeline_seed_multipipeline_execution(root, manifest, project, template, trigger if isinstance(trigger, dict) else {})
    if str(template.get("id") or "") == PATCH_SWARM_TEMPLATE_ID:
        return dev_pipeline_seed_patch_swarm_execution(root, manifest, project, template, trigger if isinstance(trigger, dict) else {})
    execution_manifest_rel, execution_manifest, _execution_steps = dev_pipeline_execution_steps(root, template)
    trigger = trigger if isinstance(trigger, dict) else {}
    run_started = datetime.now(timezone.utc)
    run_id = f"{template.get('id') or 'pipeline'}-{project.get('id') or 'project'}-{run_started.strftime('%Y%m%dT%H%M%S%fZ')}"
    is_parallel = dev_pipeline_template_is_parallel_workset(template)
    runtime_config = dev_pipeline_parallel_runtime_config(template, trigger) if is_parallel else {
        "runtime": "api-openai",
        "validation": "smoke",
        "apply_mode": "apply",
        "apply_enabled": True,
        "budget_usd": DEV_PIPELINE_DELIVERY_BUDGET_USD,
        "max_budget_usd": DEV_PIPELINE_DELIVERY_MAX_BUDGET_USD,
    }
    target_paths = dev_pipeline_delivery_target_paths(project, template, trigger)
    if is_parallel and not target_paths:
        target_paths = dev_pipeline_parallel_auto_target_paths(project, run_id, runtime_config)
    workset_rel = ""
    if target_paths:
        workset_rel, workset = dev_pipeline_delivery_workset(
            root,
            project,
            template,
            trigger,
            run_id,
            target_paths,
            float(runtime_config.get("budget_usd") or DEV_PIPELINE_DELIVERY_BUDGET_USD),
            float(runtime_config.get("max_budget_usd") or DEV_PIPELINE_DELIVERY_MAX_BUDGET_USD),
            runtime_config,
        )
    else:
        workset = {}
    readiness_errors, readiness = dev_pipeline_delivery_readiness(target_paths, workset_rel, runtime_config)
    run_status = "blocked" if readiness_errors else "running"
    run_finished = run_started if readiness_errors else None
    prompt = dev_pipeline_delivery_prompt(project, template, trigger)
    task_count = len([item for item in workset.get("tasks", []) if isinstance(item, dict)])
    max_parallel = int(workset.get("max_parallel") or 1) if isinstance(workset, dict) else 1
    runtime = str(runtime_config.get("runtime") or "api-openai")
    apply_mode = str(runtime_config.get("apply_mode") or "apply")
    validation_mode = str(runtime_config.get("validation") or "smoke")
    run_payload = {
        "schema_version": "cento.execution_run.v1",
        "source": f"cento-workset-{runtime}",
        "run_id": run_id,
        "pipeline": f"{template.get('id') or 'pipeline'}-{project.get('id') or 'project'}",
        "status": run_status,
        "started_at": run_started.isoformat(),
        "finished_at": run_finished.isoformat() if run_finished else "",
        "duration_seconds": 0,
        "triggered_by": str(trigger.get("triggered_by") or "prompt-router"),
        "issue_id": str(trigger.get("issue_id") or ""),
        "issue_subject": str(trigger.get("issue_subject") or ""),
        "prompt": prompt,
        "target_paths": target_paths,
        "workset_manifest": workset_rel,
        "workset_id": str(workset.get("id") or ""),
        "workset_max_parallel": max_parallel,
        "workset_task_count": task_count,
        "execution_model": "parallel" if is_parallel else "single",
        "runtime": runtime,
        "apply_mode": apply_mode,
        "validation_mode": validation_mode,
        "budget_usd": float(runtime_config.get("budget_usd") or 0.0),
        "max_budget_usd": float(runtime_config.get("max_budget_usd") or 0.0),
        "readiness": readiness,
        "readiness_errors": readiness_errors,
        "stages": dev_pipeline_delivery_stage_payloads(run_started, run_status, run_finished, bool(target_paths)),
        "steps": dev_pipeline_delivery_seed_steps(workset_rel, run_status, bool(target_paths), workset),
        "logs": [
            {
                "timestamp": run_started.isoformat(),
                "stage": "pipeline",
                "source": "delivery",
                "message": "Workset delivery requested",
            },
            *[
                {
                    "timestamp": run_started.isoformat(),
                    "stage": "pipeline",
                    "source": "readiness",
                    "message": error,
                }
                for error in readiness_errors
            ],
        ],
        "artifacts": [
            {"name": "workset.json", "path": workset_rel, "exists": bool(workset_rel), "size": file_size_label(ROOT_DIR / workset_rel) if workset_rel else "missing"},
            {"name": "execution_run.json", "path": dev_pipeline_relative(root / "execution" / "execution_run.json"), "exists": True, "size": "pending"},
        ],
        "facts": [
            {"label": "Engine", "value": "cento workset execute"},
            {"label": "Runtime", "value": runtime},
            {"label": "Apply", "value": "sequential integrator" if apply_mode == "apply" else "dry-run integrator"},
            {"label": "Integration model ceiling", "value": f"{DEV_PIPELINE_INTEGRATION_MODEL_CEILING} only if deterministic integration needs review"},
            {"label": "Parallel workers", "value": str(task_count) if is_parallel else "1"},
            {"label": "Max parallel", "value": str(max_parallel)},
            {"label": "Budget", "value": f"${float(runtime_config.get('budget_usd') or 0.0):.2f} target / ${float(runtime_config.get('max_budget_usd') or 0.0):.2f} cap"},
            {"label": "Target paths", "value": ", ".join(target_paths) if target_paths else "missing"},
        ],
        "written_at": datetime.now(timezone.utc).isoformat(),
    }
    dev_pipeline_write_execution_state(root, execution_manifest_rel, execution_manifest, run_payload)
    return run_payload


def dev_pipeline_run_input_allowed_fields(kind: str, source: str) -> set[str]:
    common = {"id", "kind", "source"}
    if source == "auto":
        if kind == "image":
            return common | {"image_refs", "image_notes", "answer_notes"}
        return common
    fields = {
        "text": {"answer", "answer_notes"},
        "questionnaire": {"answer", "answers", "answer_notes"},
        "path": {"paths", "answer_notes"},
        "image": {"image_refs", "image_notes", "answer_notes"},
        "details": {"answer", "answer_notes"},
        "evidence": {"artifacts", "evidence_policy", "answer_notes"},
    }
    return common | fields.get(kind, set())


def dev_pipeline_run_input_has_user_value(kind: str, item: dict[str, Any]) -> bool:
    if kind in {"text", "questionnaire", "details"}:
        if str(item.get("answer") or "").strip():
            return True
        answers = item.get("answers")
        if isinstance(answers, dict):
            return any(str(value).strip() for value in answers.values())
        if isinstance(answers, list):
            return any(str(value).strip() for value in answers)
        return False
    if kind == "path":
        return bool(dev_pipeline_text_list(item.get("paths"), []))
    if kind == "image":
        return bool(dev_pipeline_text_list(item.get("image_refs"), []))
    if kind == "evidence":
        return bool(dev_pipeline_text_list(item.get("artifacts"), []))
    return False


def dev_pipeline_run_input_answer(kind: str, item: dict[str, Any]) -> tuple[str, list[str], str]:
    notes = dev_pipeline_text(item.get("answer_notes"), "")
    if kind == "questionnaire":
        answer = dev_pipeline_text(item.get("answer"), "")
        values: list[str] = []
        answers = item.get("answers")
        if isinstance(answers, dict):
            values = [f"{key}: {value}" for key, value in answers.items() if str(value).strip()]
        elif isinstance(answers, list):
            values = [str(value) for value in answers if str(value).strip()]
        if not answer and values:
            answer = "\n".join(values)
        return answer, values, notes
    if kind in {"text", "details"}:
        return dev_pipeline_text(item.get("answer"), ""), [], notes
    if kind == "path":
        values = dev_pipeline_text_list(item.get("paths"), [])
        return "\n".join(values), values, notes
    if kind == "image":
        values = dev_pipeline_text_list(item.get("image_refs"), [])
        image_notes = dev_pipeline_text(item.get("image_notes"), "")
        return image_notes, values, notes
    if kind == "evidence":
        values = dev_pipeline_text_list(item.get("artifacts"), [])
        evidence_policy = dev_pipeline_text(item.get("evidence_policy"), "")
        return evidence_policy, values, notes
    return "", [], notes


def dev_pipeline_validate_pipeline_run_payload(payload: dict[str, Any]) -> None:
    allowed = {"schema_version", "project_id", "template_id", "inputs", "delivery_mode"}
    extras = sorted(set(payload) - allowed)
    if extras:
        raise AgentWorkAppError(f"Unexpected pipeline run field(s): {', '.join(extras)}")
    if str(payload.get("schema_version") or "") != PIPELINE_RUN_SCHEMA_VERSION:
        raise AgentWorkAppError(f"schema_version must be {PIPELINE_RUN_SCHEMA_VERSION}")
    if not str(payload.get("project_id") or "").strip():
        raise AgentWorkAppError("project_id is required")
    if not str(payload.get("template_id") or "").strip():
        raise AgentWorkAppError("template_id is required")
    if not isinstance(payload.get("inputs"), list):
        raise AgentWorkAppError("inputs must be an ordered array")
    delivery_mode = str(payload.get("delivery_mode") or "").strip()
    if delivery_mode and delivery_mode not in {"closed-loop", "plan-only"}:
        raise AgentWorkAppError("delivery_mode must be closed-loop or plan-only")


def dev_pipeline_validate_pipeline_run_inputs(template: dict[str, Any], submitted_inputs: list[Any]) -> list[dict[str, Any]]:
    contract_inputs = dev_pipeline_template_required_inputs(template)
    expected_ids = [str(item.get("id") or "") for item in contract_inputs]
    actual_ids = [str(item.get("id") or "") if isinstance(item, dict) else "" for item in submitted_inputs]
    if actual_ids != expected_ids:
        missing = [item for item in expected_ids if item not in actual_ids]
        extra = [item for item in actual_ids if item not in expected_ids]
        details = []
        if missing:
            details.append(f"missing: {', '.join(missing)}")
        if extra:
            details.append(f"extra: {', '.join(extra)}")
        if not details:
            details.append("input order does not match the selected template")
        raise AgentWorkAppError(f"inputs must match template input IDs exactly ({'; '.join(details)})")

    normalized: list[dict[str, Any]] = []
    for contract, submitted in zip(contract_inputs, submitted_inputs):
        if not isinstance(submitted, dict):
            raise AgentWorkAppError(f"input {contract.get('id')} must be an object")
        input_id = str(contract.get("id") or "")
        kind = dev_pipeline_input_type(submitted.get("kind"), str(contract.get("kind") or ""))
        contract_kind = str(contract.get("kind") or "")
        if kind not in PIPELINE_RUN_INPUT_TYPES:
            raise AgentWorkAppError(f"input {input_id} has unsupported kind: {kind}")
        if kind != contract_kind:
            raise AgentWorkAppError(f"input {input_id} kind must be {contract_kind}")
        source = dev_pipeline_input_source(submitted.get("source"), str(contract.get("source") or "user"))
        contract_source = str(contract.get("source") or "user")
        if source != contract_source:
            raise AgentWorkAppError(f"input {input_id} source must be {contract_source}")
        extras = sorted(set(submitted) - dev_pipeline_run_input_allowed_fields(kind, source))
        if extras:
            raise AgentWorkAppError(f"input {input_id} has invalid field(s) for {kind}/{source}: {', '.join(extras)}")
        if source == "user" and bool(contract.get("required", True)) and not dev_pipeline_run_input_has_user_value(kind, submitted):
            raise AgentWorkAppError(f"required user input is missing: {input_id}")
        merged = deepcopy(contract)
        merged["kind"] = kind
        merged["input_type"] = kind
        merged["source"] = source
        if source == "user":
            answer, answer_values, answer_notes = dev_pipeline_run_input_answer(kind, submitted)
            merged["answer"] = answer
            merged["answer_values"] = answer_values
            merged["answer_notes"] = answer_notes
            if kind == "path":
                merged["paths"] = answer_values
            elif kind == "image":
                merged["image_refs"] = answer_values
                merged["image_notes"] = answer
            elif kind == "evidence":
                merged["artifacts"] = answer_values
                merged["evidence_policy"] = answer
            merged["status"] = "provided" if dev_pipeline_run_input_has_user_value(kind, submitted) else str(contract.get("status") or "missing")
            merged["provided_at"] = datetime.now(timezone.utc).isoformat() if dev_pipeline_run_input_has_user_value(kind, submitted) else ""
        elif kind == "image":
            image_refs = dev_pipeline_text_list(submitted.get("image_refs"), [])
            image_notes = dev_pipeline_text(submitted.get("image_notes"), "")
            answer_notes = dev_pipeline_text(submitted.get("answer_notes"), "")
            if image_refs:
                merged["image_refs"] = list(dict.fromkeys([*image_refs, *dev_pipeline_text_list(merged.get("image_refs"), [])]))
                merged["image_notes"] = image_notes or str(merged.get("image_notes") or "")
                merged["answer_notes"] = answer_notes
                merged["status"] = "provided"
                merged["provided_at"] = datetime.now(timezone.utc).isoformat()
        normalized.append(merged)
    return dev_pipeline_required_inputs(normalized)


def dev_pipeline_prompt_from_run_inputs(inputs: list[dict[str, Any]]) -> str:
    for item in inputs:
        if str(item.get("source") or "") != "user":
            continue
        if str(item.get("id") or "") == "operator-thoughts" and str(item.get("answer") or "").strip():
            return str(item.get("answer") or "").strip()
    for item in inputs:
        if str(item.get("source") or "") == "user" and str(item.get("answer") or "").strip():
            return str(item.get("answer") or "").strip()
    return "Manual Run Pipeline request."


def dev_pipeline_start_pipeline_run(payload: dict[str, Any], *, spawn: bool = True) -> dict[str, Any]:
    dev_pipeline_validate_pipeline_run_payload(payload)
    root = DEV_PIPELINE_STUDIO_ROOT
    manifest_path = root / "pipeline_manifest.json"
    manifest = read_json_path(manifest_path)
    if not manifest:
        raise AgentWorkAppError(f"Dev Pipeline Studio manifest not found: {dev_pipeline_relative(manifest_path)}")
    if dev_pipeline_ensure_builtin_pipelines(manifest):
        write_json_path(manifest_path, manifest)

    project_id = str(payload.get("project_id") or "")
    template_id = str(payload.get("template_id") or "")
    projects = [item for item in manifest.get("projects", []) if isinstance(item, dict)]
    templates = [item for item in manifest.get("templates", []) if isinstance(item, dict)]
    project = dev_pipeline_find(projects, project_id, project_id)
    template = dev_pipeline_find(templates, template_id, template_id)
    if not project or str(project.get("id") or "") != project_id:
        raise AgentWorkAppError(f"Unknown pipeline project: {project_id}")
    if not template or str(template.get("id") or "") != template_id:
        raise AgentWorkAppError(f"Unknown pipeline template: {template_id}")

    dev_pipeline_apply_generic_blueprint(template)
    run_inputs = dev_pipeline_validate_pipeline_run_inputs(template, payload.get("inputs") if isinstance(payload.get("inputs"), list) else [])
    prompt = dev_pipeline_prompt_from_run_inputs(run_inputs)
    template["required_inputs"] = run_inputs
    execution_run = dev_pipeline_seed_execution_e2e(
        root,
        manifest,
        project,
        template,
        {
            "triggered_by": "pipeline-run-api",
            "issue_id": "",
            "issue_subject": "Run Pipeline",
            "prompt": prompt,
            "message": "Run Pipeline request accepted through input contract",
            "run_inputs": run_inputs,
            "delivery_mode": str(payload.get("delivery_mode") or ""),
        },
    )

    defaults = manifest.get("defaults") if isinstance(manifest.get("defaults"), dict) else {}
    defaults["project_id"] = project_id
    defaults["template_id"] = template_id
    manifest["defaults"] = defaults
    manifest["active_run_id"] = str(execution_run.get("run_id") or "")
    manifest["status"] = str(execution_run.get("status") or "running")
    if template_id == MULTIPIPELINE_TEMPLATE_ID:
        manifest["status_detail"] = "Run Pipeline accepted the multipipeline ProReq chain and started four sequential request-artifact passes"
    elif template_id == PROREQ_LIGHT_TEMPLATE_ID:
        mode = str(execution_run.get("delivery_mode") or "closed-loop")
        manifest["status_detail"] = f"Run Pipeline accepted ProReq-light in {mode} mode using Codex Exec instead of live Pro API dispatch"
    elif template_id == PATCH_SWARM_TEMPLATE_ID:
        manifest["status_detail"] = "Run Pipeline accepted Patch Swarm with ten ProReq patch lanes, 100+ fixture candidates, provider adapters, and one dedicated integrator"
    else:
        manifest["status_detail"] = "Run Pipeline request accepted through the selected template input contract"
    write_json_path(manifest_path, manifest)
    dev_pipeline_append_event(
        root,
        manifest,
        "pipeline_run_requested",
        project_id,
        template_id,
        {
            "execution_run_id": str(execution_run.get("run_id") or ""),
            "input_ids": [str(item.get("id") or "") for item in run_inputs],
            "delivery_mode": str(execution_run.get("delivery_mode") or ""),
        },
    )
    if spawn and execution_run.get("run_id") and str(execution_run.get("status") or "") == "running":
        dev_pipeline_spawn_execution_e2e(root, project_id, template_id, str(execution_run.get("run_id") or ""))
    route = {
        "project_id": project_id,
        "template_id": template_id,
        "run_id": str(execution_run.get("run_id") or ""),
        "status": str(execution_run.get("status") or "running"),
        "default": template_id == DEFAULT_DEV_PIPELINE_TEMPLATE_ID,
        "url": "/dev-pipeline-studio#pipeline-flow",
    }
    return {
        "schema_version": "cento.pipeline_run_response.v1",
        **route,
        "pipeline_route": route,
        "execution_run": execution_run,
    }


def dev_pipeline_latest_workset_dir(workset_id: str, since: datetime) -> Path | None:
    slug = dev_pipeline_workset_slug(workset_id)
    candidates = sorted((ROOT_DIR / ".cento" / "worksets").glob(f"{slug}_*"), key=lambda path: path.stat().st_mtime if path.exists() else 0, reverse=True)
    for path in candidates:
        try:
            modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        except OSError:
            continue
        if modified >= since - timedelta(seconds=2):
            return path
    return None


def dev_pipeline_workset_event_logs(workset_events_rel: str) -> list[dict[str, Any]]:
    if not workset_events_rel:
        return []
    rows = read_event_rows(ROOT_DIR / workset_events_rel, limit=80)
    logs: list[dict[str, Any]] = []
    for row in rows:
        timestamp = parse_iso_datetime(row.get("ts") or row.get("timestamp")) or datetime.now(timezone.utc)
        event = str(row.get("event") or "workset_event").replace("_", " ")
        task_id = str(row.get("task_id") or row.get("workset_id") or "workset")
        logs.append(
            {
                "timestamp": timestamp.isoformat(),
                "stage": "execution",
                "source": task_id,
                "message": event,
            }
        )
    return logs


def dev_pipeline_delivery_steps_from_receipt(receipt: dict[str, Any], started: datetime, finished: datetime) -> list[dict[str, Any]]:
    tasks = receipt.get("tasks") if isinstance(receipt.get("tasks"), dict) else {}
    if len(tasks) > 1 or int(receipt.get("max_parallel") or 1) > 1:
        elapsed = max(1, int(round((finished - started).total_seconds())))
        task_rows: list[dict[str, Any]] = []
        for index, (task_id, task) in enumerate(tasks.items(), start=1):
            if not isinstance(task, dict):
                continue
            task_status = dev_pipeline_execution_status_label(task.get("status") or receipt.get("status"))
            worker_title = task.get("worker_id") or task_id
            task_rows.append(
                {
                    "id": f"parallel-worker-{task_id}",
                    "title": f"Worker: {worker_title}",
                    "status": task_status,
                    "duration": duration_label(elapsed),
                    "duration_seconds": elapsed,
                    "started_at": started.isoformat(),
                    "finished_at": finished.isoformat(),
                    "file": ", ".join(str(path) for path in task.get("write_paths", []) if isinstance(path, str)) or str(task.get("api_worker_receipt") or ""),
                }
            )
        patch_status = "completed" if receipt.get("patch_bundles") else ("blocked" if receipt.get("failed_tasks") else "queued")
        integration_status = "completed" if receipt.get("integration_receipts") else ("blocked" if receipt.get("failed_tasks") else "queued")
        validation_status = "completed" if receipt.get("validation_receipts") else ("blocked" if receipt.get("failed_tasks") else "queued")
        apply_status = "completed" if receipt.get("status") == "completed" and (receipt.get("changed_paths") or str(receipt.get("apply") or "") == "none") else ("blocked" if receipt.get("failed_tasks") else "queued")
        return [
            {"id": "resolve-parallel-inputs", "title": "Resolve contract and exclusive write paths", "status": "completed", "duration": "0s", "duration_seconds": 0, "started_at": started.isoformat(), "finished_at": started.isoformat(), "file": "execution/execution_run.json"},
            {"id": "write-parallel-workset", "title": "Write parallel workset manifest", "status": "completed", "duration": "0s", "duration_seconds": 0, "started_at": started.isoformat(), "finished_at": started.isoformat(), "file": str(receipt.get("source") or "")},
            *task_rows,
            {"id": "collect-worker-artifacts", "title": "Collect worker artifacts", "status": patch_status, "duration": "0s", "duration_seconds": 0, "started_at": finished.isoformat(), "finished_at": finished.isoformat(), "file": ", ".join(str(value) for value in receipt.get("patch_bundles", []) if isinstance(value, str))},
            {"id": "integrate-sequentially", "title": "Integrate patches sequentially", "status": integration_status, "duration": "0s", "duration_seconds": 0, "started_at": finished.isoformat(), "finished_at": finished.isoformat(), "file": ", ".join(str(value) for value in receipt.get("integration_receipts", []) if isinstance(value, str))},
            {"id": "run-parallel-validation", "title": "Run parallel validation gates", "status": validation_status, "duration": "0s", "duration_seconds": 0, "started_at": finished.isoformat(), "finished_at": finished.isoformat(), "file": ", ".join(str(value) for value in receipt.get("validation_receipts", []) if isinstance(value, str))},
            {"id": "apply-worktree", "title": "Apply or confirm dry-run handoff", "status": apply_status, "duration": "0s", "duration_seconds": 0, "started_at": finished.isoformat(), "finished_at": finished.isoformat(), "file": ", ".join(str(value) for value in receipt.get("changed_paths", []) if isinstance(value, str)) or str(receipt.get("apply") or "")},
            {"id": "collect-parallel-evidence", "title": "Collect receipts, cost, and evidence", "status": "completed" if receipt else "blocked", "duration": "0s", "duration_seconds": 0, "started_at": finished.isoformat(), "finished_at": finished.isoformat(), "file": str(receipt.get("events") or "")},
        ]
    task = next(iter(tasks.values()), {}) if tasks else {}
    task_status = dev_pipeline_execution_status_label(task.get("status") or receipt.get("status"))
    elapsed = max(0, int(round((finished - started).total_seconds())))
    api_status = "completed" if task.get("api_worker_receipt") and task_status != "failed" else task_status
    patch_status = "completed" if task.get("patch_bundle") else ("blocked" if task_status in {"blocked", "failed", "rejected"} else "queued")
    integration_status = "completed" if task.get("integration_receipt") else ("blocked" if task_status in {"blocked", "failed", "rejected"} else "queued")
    apply_status = "completed" if task_status == "completed" and (task.get("apply_receipt") or str(receipt.get("apply") or "") == "none") else ("blocked" if task_status in {"blocked", "failed", "rejected"} else "queued")
    return [
        {"id": "resolve-prompt", "title": "Resolve prompt and target paths", "status": "completed", "duration": "0s", "duration_seconds": 0, "started_at": started.isoformat(), "finished_at": started.isoformat(), "file": "execution/execution_run.json"},
        {"id": "write-workset", "title": "Write executable workset", "status": "completed", "duration": "0s", "duration_seconds": 0, "started_at": started.isoformat(), "finished_at": started.isoformat(), "file": str(receipt.get("source") or "")},
        {"id": "api-worker", "title": "OpenAI patch proposal worker", "status": api_status, "duration": duration_label(max(1, elapsed)), "duration_seconds": max(1, elapsed), "started_at": started.isoformat(), "finished_at": finished.isoformat(), "file": str(task.get("api_worker_receipt") or "")},
        {"id": "materialize-patch", "title": "Materialize patch bundle", "status": patch_status, "duration": "0s", "duration_seconds": 0, "started_at": finished.isoformat(), "finished_at": finished.isoformat(), "file": str(task.get("patch_bundle") or "")},
        {"id": "integrate-sequential", "title": "Integrate patch sequentially", "status": integration_status, "duration": "0s", "duration_seconds": 0, "started_at": finished.isoformat(), "finished_at": finished.isoformat(), "file": str(task.get("integration_receipt") or "")},
        {"id": "apply-worktree", "title": "Apply or confirm dry-run handoff", "status": apply_status, "duration": "0s", "duration_seconds": 0, "started_at": finished.isoformat(), "finished_at": finished.isoformat(), "file": str(task.get("apply_receipt") or receipt.get("apply") or "")},
        {"id": "collect-receipts", "title": "Collect receipts, cost, and evidence", "status": "completed" if receipt else "blocked", "duration": "0s", "duration_seconds": 0, "started_at": finished.isoformat(), "finished_at": finished.isoformat(), "file": str(receipt.get("events") or "")},
    ]


def dev_pipeline_delivery_artifacts(run_payload: dict[str, Any], receipt: dict[str, Any]) -> list[dict[str, Any]]:
    rels: list[str] = []
    for key in ("workset_manifest", "workset_receipt", "workset_events", "stdout_log", "stderr_log"):
        if run_payload.get(key):
            rels.append(str(run_payload[key]))
    for key in ("workers", "artifacts", "patch_bundles", "integration_receipts", "validation_receipts"):
        values = receipt.get(key) if isinstance(receipt.get(key), list) else []
        rels.extend(str(value) for value in values if value)
    rels.extend(str(record.get(key) or "") for record in (receipt.get("tasks") or {}).values() for key in ("apply_receipt", "taskstream_evidence") if isinstance(record, dict) and record.get(key))
    artifacts: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rel in rels:
        clean = rel.strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        path = ROOT_DIR / clean
        artifacts.append({"name": Path(clean).name, "path": clean, "size": file_size_label(path), "exists": path.exists()})
    return artifacts


def dev_pipeline_execution_parallel_summary(run_payload: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    workset_rel = str(run_payload.get("workset_manifest") or receipt.get("source") or "")
    workset = read_json_path(ROOT_DIR / workset_rel) if workset_rel else {}
    raw_tasks = workset.get("tasks") if isinstance(workset.get("tasks"), list) else []
    receipt_tasks = receipt.get("tasks") if isinstance(receipt.get("tasks"), dict) else {}
    max_parallel = int(receipt.get("max_parallel") or run_payload.get("workset_max_parallel") or workset.get("max_parallel") or 1)
    task_count = len(raw_tasks) or int(receipt.get("total_tasks") or run_payload.get("workset_task_count") or 0)
    enabled = max_parallel > 1 or task_count > 1 or str(run_payload.get("execution_model") or workset.get("execution_model") or "") == "parallel"
    if not enabled:
        return {"enabled": False}
    tasks: list[dict[str, Any]] = []
    if raw_tasks:
        for index, task in enumerate(raw_tasks, start=1):
            if not isinstance(task, dict):
                continue
            task_id = str(task.get("id") or f"task-{index}")
            receipt_task = receipt_tasks.get(task_id) if isinstance(receipt_tasks.get(task_id), dict) else {}
            tasks.append(
                {
                    "id": task_id,
                    "title": str(task.get("task") or task_id),
                    "worker_id": str(task.get("worker_id") or receipt_task.get("worker_id") or task_id),
                    "status": dev_pipeline_execution_status_label(receipt_task.get("status") or ("queued" if run_payload.get("status") == "running" else run_payload.get("status") or "queued")),
                    "write_paths": [str(value) for value in task.get("write_paths", []) if isinstance(value, str)],
                    "depends_on": [str(value) for value in task.get("depends_on", []) if isinstance(value, str)],
                    "patch_bundle": str(receipt_task.get("patch_bundle") or ""),
                    "integration_receipt": str(receipt_task.get("integration_receipt") or ""),
                    "validation_receipt": str(receipt_task.get("validation_receipt") or ""),
                }
            )
    elif receipt_tasks:
        for task_id, receipt_task in receipt_tasks.items():
            if not isinstance(receipt_task, dict):
                continue
            tasks.append(
                {
                    "id": str(task_id),
                    "title": str(receipt_task.get("worker_id") or task_id),
                    "worker_id": str(receipt_task.get("worker_id") or task_id),
                    "status": dev_pipeline_execution_status_label(receipt_task.get("status") or receipt.get("status") or "queued"),
                    "write_paths": [str(value) for value in receipt_task.get("write_paths", []) if isinstance(value, str)],
                    "depends_on": [str(value) for value in receipt_task.get("depends_on", []) if isinstance(value, str)],
                    "patch_bundle": str(receipt_task.get("patch_bundle") or ""),
                    "integration_receipt": str(receipt_task.get("integration_receipt") or ""),
                    "validation_receipt": str(receipt_task.get("validation_receipt") or ""),
                }
            )
    return {
        "enabled": True,
        "workset_manifest": workset_rel,
        "workset_receipt": str(run_payload.get("workset_receipt") or ""),
        "max_parallel": max_parallel,
        "task_count": task_count or len(tasks),
        "integration": str(receipt.get("integration") or workset.get("integration") or "sequential"),
        "integration_model_policy": workset.get("integration_model_policy") if isinstance(workset.get("integration_model_policy"), dict) else {
            "mode": "deterministic-first",
            "fallback": "only-if-needed",
            "model_ceiling": DEV_PIPELINE_INTEGRATION_MODEL_CEILING,
            "profile": "api-mini-integrator",
        },
        "apply": str(receipt.get("apply") or run_payload.get("apply_mode") or "sequential"),
        "no_shared_files": bool(receipt.get("no_shared_files", True)),
        "summary": f"{task_count or len(tasks)} worker lanes, max {max_parallel} concurrent, one serialized integration lane",
        "tasks": tasks,
    }


def dev_pipeline_proreq_light_delivery_command() -> tuple[list[str], int]:
    runtime_profile = os.environ.get("CENTO_PROREQ_LIGHT_RUNTIME_PROFILE", "codex-fast")
    max_parallel = os.environ.get("CENTO_PROREQ_LIGHT_MAX_PARALLEL", "3")
    worker_timeout = os.environ.get("CENTO_PROREQ_LIGHT_WORKER_TIMEOUT", "180")
    delivery_timeout = int(os.environ.get("CENTO_PROREQ_LIGHT_DELIVERY_TIMEOUT", "1800"))
    command = [
        sys.executable,
        str(ROOT_DIR / "scripts" / "proreq_light.py"),
        "deliver",
        "--max-parallel",
        max_parallel,
        "--runtime-profile",
        runtime_profile,
        "--worker-timeout",
        worker_timeout,
        "--delivery-timeout",
        str(delivery_timeout),
        "--validation",
        "smoke",
        "--json",
    ]
    if os.environ.get("CENTO_PROREQ_LIGHT_NO_FULL_CHECK", "").lower() in {"1", "true", "yes", "on"}:
        command.append("--no-full-check")
    return command, delivery_timeout


def dev_pipeline_run_proreq_light_closed_loop_delivery(
    root: Path,
    execution_manifest_rel: str,
    execution_manifest: dict[str, Any],
    run_payload: dict[str, Any],
    steps: list[dict[str, Any]],
    logs: list[dict[str, Any]],
    started: datetime,
    run_id: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], bool]:
    command, delivery_timeout = dev_pipeline_proreq_light_delivery_command()
    delivery_dir = dev_pipeline_root_path(root, f"execution/delivery/{run_id}")
    delivery_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = delivery_dir / "closed-loop.stdout.log"
    stderr_path = delivery_dir / "closed-loop.stderr.log"
    stdout_rel = dev_pipeline_relative(stdout_path)
    stderr_rel = dev_pipeline_relative(stderr_path)
    delivery_started = datetime.now(timezone.utc)
    delivery_step = {
        "id": "closed-loop-delivery",
        "title": "Launch Codex workers, integrate patches, validate evidence",
        "status": "running",
        "command": shlex.join(command),
        "exit_code": None,
        "duration": "0s",
        "duration_seconds": 0,
        "started_at": delivery_started.isoformat(),
        "finished_at": "",
        "stdout_tail": "",
        "stderr_tail": "",
    }
    steps = [*steps, delivery_step]
    logs = [
        *logs,
        {
            "timestamp": delivery_started.isoformat(),
            "stage": "execution",
            "source": "closed-loop-delivery",
            "message": f"Dispatching {shlex.join(command)}",
        },
    ][-120:]
    run_payload["steps"] = steps
    run_payload["logs"] = logs
    run_payload["stdout_log"] = stdout_rel
    run_payload["stderr_log"] = stderr_rel
    dev_pipeline_write_execution_state(root, execution_manifest_rel, execution_manifest, run_payload)

    stdout = ""
    stderr = ""
    returncode: int | None = None
    timed_out = False
    try:
        proc = subprocess.run(
            command,
            cwd=ROOT_DIR,
            text=True,
            capture_output=True,
            timeout=delivery_timeout + 30,
            check=False,
        )
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        returncode = proc.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        stderr = (stderr + f"\nTimed out after {delivery_timeout + 30}s.\n").strip()

    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    delivery_finished = datetime.now(timezone.utc)
    duration_seconds = max(1, int(round((delivery_finished - delivery_started).total_seconds())))
    try:
        delivery_payload = json.loads(stdout or "{}")
    except json.JSONDecodeError:
        delivery_payload = {}
    if not isinstance(delivery_payload, dict) or not delivery_payload:
        delivery_payload = read_json_path(
            ROOT_DIR / f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/{run_id}/closed_loop_delivery.json"
        )
    delivery_status = str(delivery_payload.get("status") or ("timeout" if timed_out else "blocked"))
    step_status = "completed" if delivery_status == "completed" and returncode == 0 else "blocked"
    receipt_rel = str(delivery_payload.get("workset_receipt") or "")
    receipt = read_json_path(ROOT_DIR / receipt_rel) if receipt_rel else {}
    workset_result = delivery_payload.get("workset_result") if isinstance(delivery_payload.get("workset_result"), dict) else {}
    if receipt:
        run_payload["workset_receipt"] = receipt_rel
        run_payload["workset_dir"] = str(workset_result.get("workset_dir") or receipt.get("workset_dir") or "")
        run_payload["workset_events"] = str(receipt.get("events") or "")
        run_payload["total_ai_cost_usd"] = float(receipt.get("total_cost_usd") or 0.0)
        run_payload["changed_paths"] = [str(value) for value in receipt.get("changed_paths", []) if isinstance(value, str)]
    else:
        run_payload["total_ai_cost_usd"] = 0.0
        run_payload["changed_paths"] = []
    run_payload["closed_loop_delivery"] = str(
        delivery_payload.get("delivery")
        or f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/{run_id}/closed_loop_delivery.json"
    )
    run_payload["closed_loop_evidence"] = f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/{run_id}/closed_loop_evidence.json"
    run_payload["closed_loop_incident"] = str(delivery_payload.get("incident") or "")
    run_payload["artifacts"] = dev_pipeline_hard_proreq_artifacts(run_id)
    run_payload["facts"] = [
        {"label": "Engine", "value": "cento proreq-light deliver"},
        {"label": "Runtime", "value": f"local-command / {delivery_payload.get('runtime_profile') or os.environ.get('CENTO_PROREQ_LIGHT_RUNTIME_PROFILE', 'codex-fast')}"},
        {"label": "Apply", "value": str(delivery_payload.get("apply") or "clean-owned-paths")},
        {"label": "Parallel workers", "value": str(receipt.get("total_tasks") or len((receipt.get("tasks") or {}) if isinstance(receipt.get("tasks"), dict) else {}))},
        {"label": "Max parallel", "value": str(delivery_payload.get("max_parallel") or os.environ.get("CENTO_PROREQ_LIGHT_MAX_PARALLEL", "3"))},
        {"label": "AI cost", "value": f"${float(run_payload.get('total_ai_cost_usd') or 0.0):.6f} local ledger; dashboard remains source of truth"},
        {"label": "Changed paths", "value": ", ".join(run_payload["changed_paths"]) if run_payload["changed_paths"] else "none"},
    ]
    steps[-1] = {
        **delivery_step,
        "status": step_status,
        "exit_code": returncode,
        "duration": duration_label(duration_seconds),
        "duration_seconds": duration_seconds,
        "finished_at": delivery_finished.isoformat(),
        "stdout_tail": stdout[-1200:],
        "stderr_tail": stderr[-1200:],
    }
    logs = [
        *logs,
        *dev_pipeline_workset_event_logs(str(run_payload.get("workset_events") or "")),
        {
            "timestamp": delivery_finished.isoformat(),
            "stage": "handoff",
            "source": "closed-loop-delivery",
            "message": f"ProReq-light closed-loop delivery finished with status {delivery_status}",
            "exit_code": returncode,
        },
    ][-120:]
    run_payload["steps"] = steps
    run_payload["logs"] = logs
    dev_pipeline_write_execution_state(root, execution_manifest_rel, execution_manifest, run_payload)
    return run_payload, steps, logs, step_status != "completed"


def dev_pipeline_finish_hard_proreq_execution(root: Path, project_id: str, template_id: str, run_id: str) -> None:
    manifest_path = root / "pipeline_manifest.json"
    manifest = read_json_path(manifest_path)
    if not manifest:
        return
    templates = [item for item in manifest.get("templates", []) if isinstance(item, dict)]
    projects = [item for item in manifest.get("projects", []) if isinstance(item, dict)]
    project = dev_pipeline_find(projects, project_id, project_id)
    template = dev_pipeline_find(templates, template_id, template_id)
    if not project or not template:
        return
    dev_pipeline_apply_generic_blueprint(template)
    execution_manifest_rel = str(template.get("execution_manifest") or "execution/execution_manifest.json")
    execution_manifest = {}
    run_payload = dev_pipeline_artifact_json(root, f"execution/runs/{run_id}.json") or dev_pipeline_artifact_json(root, "execution/execution_run.json")
    if str(run_payload.get("run_id") or "") != run_id or str(run_payload.get("status") or "") != "running":
        return
    is_light = str(template_id or template.get("id") or "") == PROREQ_LIGHT_TEMPLATE_ID or str(run_payload.get("source") or "").startswith("cento-proreq-light")
    started = parse_iso_datetime(run_payload.get("started_at")) or datetime.now(timezone.utc)
    steps = [dict(step) for step in run_payload.get("steps", []) if isinstance(step, dict)]
    logs = [item for item in run_payload.get("logs", []) if isinstance(item, dict)]
    run_failed = False
    run_blocked = False
    for index, step in enumerate(steps):
        step_id = str(step.get("id") or f"step-{index + 1}")
        command = dev_pipeline_execution_command_for_step(step_id)
        if is_light and step_id == "write-ui-screenshot-request":
            command = ["python3", "scripts/dev_pipeline_hard_proreq.py", "light-screenshot"]
        step_started = datetime.now(timezone.utc)
        steps[index] = {
            **step,
            "status": "running",
            "started_at": step_started.isoformat(),
            "finished_at": "",
            "command": shlex.join(command),
        }
        run_payload["steps"] = steps
        run_payload["stages"] = dev_pipeline_hard_proreq_stage_payloads(started, "running")
        logs.append({"timestamp": step_started.isoformat(), "stage": "execution", "source": step_id, "message": f"{step.get('title') or step_id} started", "command": shlex.join(command)})
        run_payload["logs"] = logs[-100:]
        dev_pipeline_write_execution_state(root, execution_manifest_rel, execution_manifest, run_payload)

        step_timeout = int(os.environ.get("CENTO_HARD_PROREQ_STEP_TIMEOUT", "90"))
        if step_id == "write-ui-screenshot-request":
            step_timeout = int(os.environ.get("CENTO_HARD_PROREQ_STEP_TIMEOUT", "90")) if is_light else int(os.environ.get("CENTO_HARD_PROREQ_IMAGE_TIMEOUT", "240")) + 30
        if step_id == "dispatch-codex-pro-backend-plan":
            step_timeout = int(os.environ.get("CENTO_PROREQ_LIGHT_CODEX_TIMEOUT", "900")) + 30
        result = subprocess.run(command, cwd=ROOT_DIR, text=True, capture_output=True, timeout=step_timeout)
        elapsed = (datetime.now(timezone.utc) - step_started).total_seconds()
        if elapsed < DEV_PIPELINE_EXECUTION_MIN_STEP_SECONDS:
            time.sleep(DEV_PIPELINE_EXECUTION_MIN_STEP_SECONDS - elapsed)
        step_finished = datetime.now(timezone.utc)
        duration_seconds = max(1, int(round((step_finished - step_started).total_seconds())))
        muted_step = bool(step.get("muted")) or str(step.get("lane") or "") == "frontend"
        status = "muted" if muted_step and result.returncode == 0 else ("completed" if result.returncode == 0 else "failed")
        if result.returncode != 0:
            run_failed = True
        steps[index] = {
            **step,
            "id": step_id,
            "title": str(step.get("title") or step_id),
            "status": status,
            "command": shlex.join(command),
            "exit_code": result.returncode,
            "duration": duration_label(duration_seconds),
            "duration_seconds": duration_seconds,
            "started_at": step_started.isoformat(),
            "finished_at": step_finished.isoformat(),
            "stdout_tail": result.stdout[-1200:],
            "stderr_tail": result.stderr[-1200:],
        }
        logs.append({"timestamp": step_finished.isoformat(), "stage": "execution", "source": step_id, "message": f"{step.get('title') or step_id} finished with status {status}", "exit_code": result.returncode})
        run_payload["steps"] = steps
        run_payload["logs"] = logs[-120:]
        run_payload["artifacts"] = dev_pipeline_hard_proreq_artifacts(run_id)
        dev_pipeline_write_execution_state(root, execution_manifest_rel, execution_manifest, run_payload)
        if run_failed:
            break

    if is_light and not run_failed and str(run_payload.get("delivery_mode") or "closed-loop") == "closed-loop":
        run_payload, steps, logs, delivery_blocked = dev_pipeline_run_proreq_light_closed_loop_delivery(
            root,
            execution_manifest_rel,
            execution_manifest,
            run_payload,
            steps,
            logs,
            started,
            run_id,
        )
        run_blocked = bool(delivery_blocked)

    finished = datetime.now(timezone.utc)
    run_status = "failed" if run_failed else ("blocked" if run_blocked else "completed")
    if run_failed:
        for index in range(index + 1, len(steps)):
            steps[index] = {**steps[index], "status": "blocked", "stderr_tail": "Skipped because an upstream hard proreq step failed."}
    run_payload["status"] = run_status
    run_payload["finished_at"] = finished.isoformat()
    run_payload["duration_seconds"] = max(0, int(round((finished - started).total_seconds())))
    run_payload["stages"] = dev_pipeline_hard_proreq_stage_payloads(started, run_status, finished)
    run_payload["steps"] = steps
    run_payload["logs"] = [
        *logs,
        {
            "timestamp": finished.isoformat(),
            "stage": "handoff",
            "source": "proreq-light" if is_light else "hard-proreq",
            "message": ("ProReq-light closed-loop run finished" if is_light and str(run_payload.get("delivery_mode") or "") == "closed-loop" else ("ProReq-light Codex Exec planning finished" if is_light else "Hard proreq planning finished")) + f" with status {run_status}",
        },
    ][-120:]
    run_payload["artifacts"] = dev_pipeline_hard_proreq_artifacts(run_id)
    run_payload["written_at"] = datetime.now(timezone.utc).isoformat()
    dev_pipeline_write_execution_state(root, execution_manifest_rel, execution_manifest, run_payload)

    manifest["active_run_id"] = run_id
    manifest["status"] = run_status
    manifest["status_detail"] = (
        (
            "ProReq-light closed-loop pipeline completed; Codex Exec simulated the Pro planning lane, launched local Codex workers, integrated accepted patches, and wrote validation evidence"
            if run_status == "completed"
            else "ProReq-light closed-loop pipeline blocked; incident and closed-loop evidence artifacts were written for follow-up"
        )
        if is_light
        else "Hard proreq pipeline completed; GPT pro backend request, schema, Cento context, muted frontend request, backend work, integration, and validation artifacts are ready"
    )
    write_json_path(manifest_path, manifest)
    dev_pipeline_append_event(
        root,
        manifest,
        "pipeline_proreq_light_finished" if is_light else "pipeline_hard_proreq_finished",
        str(project.get("id") or project_id),
        str(template.get("id") or template_id),
        {"execution_run_id": run_id, "status": run_status, "artifacts": [item["path"] for item in dev_pipeline_hard_proreq_artifacts(run_id)]},
    )


def dev_pipeline_finish_multipipeline_execution(root: Path, project_id: str, template_id: str, run_id: str) -> None:
    manifest_path = root / "pipeline_manifest.json"
    manifest = read_json_path(manifest_path)
    if not manifest:
        return
    templates = [item for item in manifest.get("templates", []) if isinstance(item, dict)]
    projects = [item for item in manifest.get("projects", []) if isinstance(item, dict)]
    project = dev_pipeline_find(projects, project_id, project_id)
    template = dev_pipeline_find(templates, template_id, template_id)
    if not project or not template:
        return
    dev_pipeline_apply_generic_blueprint(template)
    execution_manifest_rel = str(template.get("execution_manifest") or "execution/multipipeline_execution_manifest.json")
    execution_manifest = {}
    run_payload = dev_pipeline_artifact_json(root, f"execution/runs/{run_id}.json") or dev_pipeline_artifact_json(root, "execution/execution_run.json")
    if str(run_payload.get("run_id") or "") != run_id or str(run_payload.get("status") or "") != "running":
        return
    started = parse_iso_datetime(run_payload.get("started_at")) or datetime.now(timezone.utc)
    steps = [dict(step) for step in run_payload.get("steps", []) if isinstance(step, dict)]
    logs = [item for item in run_payload.get("logs", []) if isinstance(item, dict)]
    run_failed = False
    env = os.environ.copy()
    env["CENTO_DEV_PIPELINE_STUDIO_ROOT"] = str(root)
    for index, step in enumerate(steps):
        step_id = str(step.get("id") or f"step-{index + 1}")
        command = dev_pipeline_execution_command_for_step(step_id)
        step_started = datetime.now(timezone.utc)
        steps[index] = {
            **step,
            "status": "running",
            "started_at": step_started.isoformat(),
            "finished_at": "",
            "command": shlex.join(command),
        }
        run_payload["steps"] = steps
        run_payload["stages"] = dev_pipeline_multipipeline_stage_payloads(started, "running")
        logs.append({"timestamp": step_started.isoformat(), "stage": "execution", "source": step_id, "message": f"{step.get('title') or step_id} started", "command": shlex.join(command)})
        run_payload["logs"] = logs[-100:]
        dev_pipeline_write_execution_state(root, execution_manifest_rel, execution_manifest, run_payload)

        step_timeout = int(os.environ.get("CENTO_MULTIPIPELINE_STEP_TIMEOUT", "60"))
        result = subprocess.run(command, cwd=ROOT_DIR, text=True, capture_output=True, timeout=step_timeout, env=env)
        elapsed = (datetime.now(timezone.utc) - step_started).total_seconds()
        if elapsed < DEV_PIPELINE_EXECUTION_MIN_STEP_SECONDS:
            time.sleep(DEV_PIPELINE_EXECUTION_MIN_STEP_SECONDS - elapsed)
        step_finished = datetime.now(timezone.utc)
        duration_seconds = max(1, int(round((step_finished - step_started).total_seconds())))
        muted_step = bool(step.get("muted")) or str(step.get("lane") or "") == "frontend"
        status = "muted" if muted_step and result.returncode == 0 else ("completed" if result.returncode == 0 else "failed")
        if result.returncode != 0:
            run_failed = True
        steps[index] = {
            **step,
            "id": step_id,
            "title": str(step.get("title") or step_id),
            "status": status,
            "command": shlex.join(command),
            "exit_code": result.returncode,
            "duration": duration_label(duration_seconds),
            "duration_seconds": duration_seconds,
            "started_at": step_started.isoformat(),
            "finished_at": step_finished.isoformat(),
            "stdout_tail": result.stdout[-1200:],
            "stderr_tail": result.stderr[-1200:],
        }
        logs.append({"timestamp": step_finished.isoformat(), "stage": "execution", "source": step_id, "message": f"{step.get('title') or step_id} finished with status {status}", "exit_code": result.returncode})
        run_payload["steps"] = steps
        run_payload["logs"] = logs[-120:]
        run_payload["artifacts"] = dev_pipeline_multipipeline_artifacts(run_id)
        dev_pipeline_write_execution_state(root, execution_manifest_rel, execution_manifest, run_payload)
        if run_failed:
            break

    finished = datetime.now(timezone.utc)
    run_status = "failed" if run_failed else "completed"
    if run_failed:
        for blocked_index in range(index + 1, len(steps)):
            steps[blocked_index] = {**steps[blocked_index], "status": "blocked", "stderr_tail": "Skipped because an upstream multipipeline ProReq step failed."}
    run_payload["status"] = run_status
    run_payload["finished_at"] = finished.isoformat()
    run_payload["duration_seconds"] = max(0, int(round((finished - started).total_seconds())))
    run_payload["stages"] = dev_pipeline_multipipeline_stage_payloads(started, run_status, finished)
    run_payload["steps"] = steps
    run_payload["logs"] = [
        *logs,
        {"timestamp": finished.isoformat(), "stage": "handoff", "source": "multipipeline-proreq", "message": f"Multipipeline ProReq chain finished with status {run_status}"},
    ][-120:]
    run_payload["artifacts"] = dev_pipeline_multipipeline_artifacts(run_id)
    run_payload["written_at"] = datetime.now(timezone.utc).isoformat()
    dev_pipeline_write_execution_state(root, execution_manifest_rel, execution_manifest, run_payload)

    manifest["active_run_id"] = run_id
    manifest["status"] = run_status
    manifest["status_detail"] = "Multipipeline ProReq chain completed; four sequential pass requests, UI screenshot request, ChatGPT Pro request, roadmap, and evidence artifacts are ready"
    write_json_path(manifest_path, manifest)
    dev_pipeline_append_event(
        root,
        manifest,
        "pipeline_multipipeline_proreq_finished",
        str(project.get("id") or project_id),
        str(template.get("id") or template_id),
        {"execution_run_id": run_id, "status": run_status, "artifacts": [item["path"] for item in dev_pipeline_multipipeline_artifacts(run_id)]},
    )


def dev_pipeline_finish_patch_swarm_execution(root: Path, project_id: str, template_id: str, run_id: str) -> None:
    manifest_path = root / "pipeline_manifest.json"
    manifest = read_json_path(manifest_path)
    if not manifest:
        return
    templates = [item for item in manifest.get("templates", []) if isinstance(item, dict)]
    projects = [item for item in manifest.get("projects", []) if isinstance(item, dict)]
    project = dev_pipeline_find(projects, project_id, project_id)
    template = dev_pipeline_find(templates, template_id, template_id)
    if not project or not template:
        return
    dev_pipeline_apply_generic_blueprint(template)
    execution_manifest_rel = str(template.get("execution_manifest") or "execution/patch_swarm_execution_manifest.json")
    execution_manifest = {}
    run_payload = dev_pipeline_artifact_json(root, f"execution/runs/{run_id}.json") or dev_pipeline_artifact_json(root, "execution/execution_run.json")
    if str(run_payload.get("run_id") or "") != run_id or str(run_payload.get("status") or "") != "running":
        return
    started = parse_iso_datetime(run_payload.get("started_at")) or datetime.now(timezone.utc)
    steps = [dict(step) for step in run_payload.get("steps", []) if isinstance(step, dict)]
    logs = [item for item in run_payload.get("logs", []) if isinstance(item, dict)]
    command = [
        sys.executable,
        str(ROOT_DIR / "scripts" / "parallel_delivery.py"),
        "patch-swarm",
        "e2e",
        "--run-id",
        run_id,
        "--objective",
        str(run_payload.get("prompt") or "Patch Swarm UI request."),
        "--candidate-target",
        str(int(run_payload.get("candidate_target") or 100)),
        "--max-parallel-agents",
        str(int(run_payload.get("max_parallel_agents") or 5)),
        "--providers",
        str(run_payload.get("providers") or "codex-exec,claude-code,api-openai"),
        "--fixture",
        "--json",
    ]
    run_payload["logs"] = [
        *logs,
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stage": "execution",
            "source": "patch-swarm",
            "message": f"Dispatching {shlex.join(command)}",
        },
    ][-120:]
    for index, step in enumerate(steps):
        steps[index] = {**step, "status": "running", "started_at": datetime.now(timezone.utc).isoformat(), "command": shlex.join(command)}
    run_payload["steps"] = steps
    dev_pipeline_write_execution_state(root, execution_manifest_rel, execution_manifest, run_payload)

    proc = subprocess.run(command, cwd=ROOT_DIR, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=int(os.environ.get("CENTO_PATCH_SWARM_UI_TIMEOUT", "300")), check=False)
    finished = datetime.now(timezone.utc)
    duration_seconds = max(1, int(round((finished - started).total_seconds())))
    try:
        result = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        result = {}
    run_status = "completed" if proc.returncode == 0 and result.get("status") == "completed" else "blocked"
    for index, step in enumerate(steps):
        step_id = str(step.get("id") or "")
        is_integrator = step_id == "dedicated-integrator"
        steps[index] = {
            **step,
            "status": run_status if is_integrator else ("completed" if run_status == "completed" else "blocked"),
            "exit_code": proc.returncode,
            "duration": duration_label(duration_seconds),
            "duration_seconds": duration_seconds,
            "finished_at": finished.isoformat(),
            "stdout_tail": (proc.stdout or "")[-1200:],
            "stderr_tail": (proc.stderr or "")[-1200:],
        }
    run_payload["status"] = run_status
    run_payload["finished_at"] = finished.isoformat()
    run_payload["duration_seconds"] = duration_seconds
    run_payload["stages"] = dev_pipeline_patch_swarm_stage_payloads(started, run_status, finished)
    run_payload["steps"] = steps
    run_payload["logs"] = [
        *run_payload.get("logs", []),
        {
            "timestamp": finished.isoformat(),
            "stage": "handoff",
            "source": "patch-swarm",
            "message": f"Patch Swarm finished with status {run_status}",
            "exit_code": proc.returncode,
        },
    ][-120:]
    run_payload["patch_swarm_run_dir"] = str(result.get("run_dir") or f"workspace/runs/parallel-delivery/patch-swarm/{run_id}")
    run_payload["candidate_count"] = int(result.get("candidate_count") or 0)
    run_payload["selected_count"] = int(result.get("selected_count") or 0)
    run_payload["safe_integrator_handoff"] = str(result.get("safe_integrator_handoff") or "")
    run_payload["total_ai_cost_usd"] = float(result.get("estimated_cost_usd") or 0.0)
    run_payload["artifacts"] = dev_pipeline_patch_swarm_artifacts(run_id)
    run_payload["facts"] = [
        {"label": "Engine", "value": "cento parallel-delivery patch-swarm e2e"},
        {"label": "Providers", "value": str(run_payload.get("providers") or "codex-exec,claude-code,api-openai")},
        {"label": "Candidates", "value": str(run_payload.get("candidate_count") or result.get("candidate_count") or 0)},
        {"label": "Selected", "value": str(run_payload.get("selected_count") or result.get("selected_count") or 0)},
        {"label": "AI cost", "value": f"${float(run_payload.get('total_ai_cost_usd') or 0.0):.6f} fixture ledger"},
        {"label": "Handoff", "value": str(run_payload.get("safe_integrator_handoff") or "pending")},
    ]
    run_payload["written_at"] = datetime.now(timezone.utc).isoformat()
    dev_pipeline_write_execution_state(root, execution_manifest_rel, execution_manifest, run_payload)

    manifest["active_run_id"] = run_id
    manifest["status"] = run_status
    manifest["status_detail"] = f"Patch Swarm {run_status}; candidates={run_payload.get('candidate_count', 0)} selected={run_payload.get('selected_count', 0)} cost=${float(run_payload.get('total_ai_cost_usd') or 0.0):.6f}"
    budget = manifest.get("budget") if isinstance(manifest.get("budget"), dict) else {}
    budget["spent_usd"] = float(run_payload.get("total_ai_cost_usd") or 0.0)
    budget["cap_usd"] = 20.0
    manifest["budget"] = budget
    template["budget_spent_usd"] = budget["spent_usd"]
    template["budget_cap_usd"] = budget["cap_usd"]
    write_json_path(manifest_path, manifest)
    dev_pipeline_append_event(
        root,
        manifest,
        "pipeline_patch_swarm_finished",
        str(project.get("id") or project_id),
        str(template.get("id") or template_id),
        {"execution_run_id": run_id, "status": run_status, "candidate_count": run_payload.get("candidate_count", 0), "selected_count": run_payload.get("selected_count", 0)},
    )


def dev_pipeline_finish_execution_e2e(root: Path, project_id: str, template_id: str, run_id: str) -> None:
    with DEV_PIPELINE_EXECUTION_LOCK:
        if str(template_id or "") in {HARD_PROREQ_TEMPLATE_ID, PROREQ_LIGHT_TEMPLATE_ID}:
            dev_pipeline_finish_hard_proreq_execution(root, project_id, template_id, run_id)
            return
        if str(template_id or "") == MULTIPIPELINE_TEMPLATE_ID:
            dev_pipeline_finish_multipipeline_execution(root, project_id, template_id, run_id)
            return
        if str(template_id or "") == PATCH_SWARM_TEMPLATE_ID:
            dev_pipeline_finish_patch_swarm_execution(root, project_id, template_id, run_id)
            return
        manifest_path = root / "pipeline_manifest.json"
        manifest = read_json_path(manifest_path)
        if not manifest:
            return
        templates = [item for item in manifest.get("templates", []) if isinstance(item, dict)]
        projects = [item for item in manifest.get("projects", []) if isinstance(item, dict)]
        project = dev_pipeline_find(projects, project_id, project_id)
        template = dev_pipeline_find(templates, template_id, template_id)
        if not project or not template:
            return
        execution_manifest_rel, execution_manifest, _execution_steps = dev_pipeline_execution_steps(root, template)
        run_payload = dev_pipeline_artifact_json(root, f"execution/runs/{run_id}.json") or dev_pipeline_artifact_json(root, "execution/execution_run.json")
        if str(run_payload.get("run_id") or "") != run_id or str(run_payload.get("status") or "") != "running":
            return
        started = parse_iso_datetime(run_payload.get("started_at")) or datetime.now(timezone.utc)
        delivery_dir_rel = f"execution/delivery/{run_id}"
        delivery_dir = dev_pipeline_root_path(root, delivery_dir_rel)
        delivery_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = delivery_dir / "workset.stdout.log"
        stderr_path = delivery_dir / "workset.stderr.log"
        stdout_rel = dev_pipeline_relative(stdout_path)
        stderr_rel = dev_pipeline_relative(stderr_path)
        workset_rel = str(run_payload.get("workset_manifest") or "")
        if DEV_PIPELINE_DELIVERY_REDIRECT_GRACE_SECONDS > 0:
            run_payload["logs"] = [
                *[item for item in run_payload.get("logs", []) if isinstance(item, dict)],
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "stage": "pipeline",
                    "source": "redirect",
                    "message": f"Waiting {DEV_PIPELINE_DELIVERY_REDIRECT_GRACE_SECONDS:.1f}s before worker dispatch so the browser can land on Execution Flow",
                },
            ][-80:]
            run_payload["stdout_log"] = stdout_rel
            run_payload["stderr_log"] = stderr_rel
            dev_pipeline_write_execution_state(root, execution_manifest_rel, execution_manifest, run_payload)
            time.sleep(DEV_PIPELINE_DELIVERY_REDIRECT_GRACE_SECONDS)
        runtime = str(run_payload.get("runtime") or "api-openai")
        apply_mode = str(run_payload.get("apply_mode") or "apply")
        validation_mode = str(run_payload.get("validation_mode") or "smoke")
        command = [
            sys.executable,
            str(ROOT_DIR / "scripts" / "cento_workset.py"),
            "execute",
            workset_rel,
            "--runtime",
            runtime,
            "--integrate",
            "sequential",
            "--validation",
            validation_mode,
            "--worker-timeout",
            str(DEV_PIPELINE_DELIVERY_TIMEOUT_SECONDS),
        ]
        if runtime == "api-openai":
            command.extend(
                [
                    "--api-profile",
                    DEV_PIPELINE_DELIVERY_API_PROFILE,
                    "--budget-usd",
                    f"{float(run_payload.get('budget_usd') or DEV_PIPELINE_DELIVERY_BUDGET_USD):.2f}",
                    "--max-budget-usd",
                    f"{float(run_payload.get('max_budget_usd') or DEV_PIPELINE_DELIVERY_MAX_BUDGET_USD):.2f}",
                ]
            )
        elif runtime == "fixture":
            command.extend(["--fixture-case", "valid"])
        if apply_mode == "apply":
            command.append("--apply")
        else:
            command.append("--allow-dirty-owned")
        command.extend(
            [
            "--json",
            ]
        )
        running_steps = [dict(step) for step in run_payload.get("steps", []) if isinstance(step, dict)]
        for index, step in enumerate(running_steps):
            step_id = str(step.get("id") or "")
            if step_id == "api-worker" or step_id.startswith("parallel-worker-") or step_id == "dispatch-parallel-workers":
                running_steps[index] = {**step, "status": "running", "started_at": datetime.now(timezone.utc).isoformat(), "command": shlex.join(command)}
        run_payload["steps"] = running_steps
        run_payload["logs"] = [
            *[item for item in run_payload.get("logs", []) if isinstance(item, dict)],
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "stage": "execution",
                "source": "workset",
                "message": f"Dispatching {shlex.join(command)}",
            },
        ]
        run_payload["stdout_log"] = stdout_rel
        run_payload["stderr_log"] = stderr_rel
        dev_pipeline_write_execution_state(root, execution_manifest_rel, execution_manifest, run_payload)

        proc = subprocess.Popen(command, cwd=ROOT_DIR, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        workset_dir: Path | None = None
        while proc.poll() is None:
            if workset_dir is None:
                workset_dir = dev_pipeline_latest_workset_dir(str(run_payload.get("workset_id") or ""), started)
                if workset_dir is not None:
                    run_payload["workset_dir"] = dev_pipeline_relative(workset_dir)
                    run_payload["workset_events"] = dev_pipeline_relative(workset_dir / "events.ndjson")
                    run_payload["logs"] = [
                        *[item for item in run_payload.get("logs", []) if isinstance(item, dict)],
                        *dev_pipeline_workset_event_logs(str(run_payload.get("workset_events") or "")),
                    ][-80:]
                    dev_pipeline_write_execution_state(root, execution_manifest_rel, execution_manifest, run_payload)
            time.sleep(0.8)
        stdout, stderr = proc.communicate()
        stdout_path.write_text(stdout or "", encoding="utf-8")
        stderr_path.write_text(stderr or "", encoding="utf-8")

        result: dict[str, Any] = {}
        try:
            result = json.loads(stdout or "{}")
        except json.JSONDecodeError:
            result = {}
        receipt_rel = str(result.get("workset_receipt") or "")
        receipt = read_json_path(ROOT_DIR / receipt_rel) if receipt_rel else {}
        finished = datetime.now(timezone.utc)
        if receipt:
            status = dev_pipeline_execution_status_label(receipt.get("status"))
            run_payload["workset_receipt"] = receipt_rel
            run_payload["workset_dir"] = str(result.get("workset_dir") or run_payload.get("workset_dir") or "")
            run_payload["workset_events"] = str(receipt.get("events") or run_payload.get("workset_events") or "")
            run_payload["total_ai_cost_usd"] = float(receipt.get("total_cost_usd") or 0.0)
            run_payload["changed_paths"] = [str(value) for value in receipt.get("changed_paths", []) if isinstance(value, str)]
            run_payload["steps"] = dev_pipeline_delivery_steps_from_receipt(receipt, started, finished)
            run_payload["artifacts"] = dev_pipeline_delivery_artifacts(run_payload, receipt)
            apply_label = "dry-run integrator" if str(receipt.get("apply") or "") == "none" else ("sequential integrator" if int(receipt.get("total_tasks") or len(receipt.get("tasks") or {}) or 1) > 1 else "direct worktree")
            run_payload["facts"] = [
                {"label": "Engine", "value": "cento workset execute"},
                {"label": "Runtime", "value": str(receipt.get("runtime") or "api-openai")},
                {"label": "Apply", "value": apply_label},
                {"label": "Integration model ceiling", "value": f"{DEV_PIPELINE_INTEGRATION_MODEL_CEILING} only if needed"},
                {"label": "Parallel workers", "value": str(receipt.get("total_tasks") or len(receipt.get("tasks") or {}))},
                {"label": "Max parallel", "value": str(receipt.get("max_parallel") or run_payload.get("workset_max_parallel") or 1)},
                {"label": "AI cost", "value": f"${float(receipt.get('total_cost_usd') or 0.0):.6f}"},
                {"label": "Budget", "value": f"${float(receipt.get('target_budget_usd') or 0.0):.2f} target / ${float(receipt.get('max_budget_usd') or 0.0):.2f} cap"},
                {"label": "Changed paths", "value": ", ".join(run_payload["changed_paths"]) if run_payload["changed_paths"] else "none"},
            ]
        else:
            status = "failed"
            run_payload["steps"] = [
                {**step, "status": "failed" if str(step.get("id") or "") == "api-worker" else dev_pipeline_execution_status_label(step.get("status"))}
                for step in run_payload.get("steps", [])
                if isinstance(step, dict)
            ]
            run_payload["artifacts"] = dev_pipeline_delivery_artifacts(run_payload, {})
        run_status = "completed" if status == "completed" and proc.returncode == 0 else ("blocked" if status in {"blocked", "rejected"} else status)
        run_payload["status"] = run_status
        run_payload["finished_at"] = finished.isoformat()
        run_payload["duration_seconds"] = max(0, int(round((finished - started).total_seconds())))
        run_payload["stages"] = dev_pipeline_delivery_stage_payloads(started, run_status, finished, bool(run_payload.get("target_paths")))
        run_payload["logs"] = [
            *[item for item in run_payload.get("logs", []) if isinstance(item, dict)],
            *dev_pipeline_workset_event_logs(str(run_payload.get("workset_events") or "")),
            {
                "timestamp": finished.isoformat(),
                "stage": "handoff",
                "source": "workset",
                "message": f"Workset delivery finished with status {run_status}",
            },
        ][-120:]
        run_payload["written_at"] = datetime.now(timezone.utc).isoformat()
        dev_pipeline_write_execution_state(root, execution_manifest_rel, execution_manifest, run_payload)

        manifest["active_run_id"] = run_id
        manifest["status"] = run_status
        manifest["status_detail"] = f"Workset delivery {run_status}; AI cost ${float(run_payload.get('total_ai_cost_usd') or 0.0):.6f}; changed paths: {', '.join(run_payload.get('changed_paths') or []) or 'none'}"
        budget = manifest.get("budget") if isinstance(manifest.get("budget"), dict) else {}
        budget["spent_usd"] = float(run_payload.get("total_ai_cost_usd") or 0.0)
        budget["cap_usd"] = float(run_payload.get("max_budget_usd") or DEV_PIPELINE_DELIVERY_MAX_BUDGET_USD)
        manifest["budget"] = budget
        template["budget_spent_usd"] = budget["spent_usd"]
        template["budget_cap_usd"] = budget["cap_usd"]
        write_json_path(manifest_path, manifest)
        dev_pipeline_append_event(
            root,
            manifest,
            "pipeline_workset_delivery_finished",
            str(project.get("id") or project_id),
            str(template.get("id") or template_id),
            {
                "execution_run_id": run_id,
                "status": run_status,
                "workset_receipt": str(run_payload.get("workset_receipt") or ""),
                "total_ai_cost_usd": float(run_payload.get("total_ai_cost_usd") or 0.0),
                "changed_paths": run_payload.get("changed_paths") or [],
            },
        )


def dev_pipeline_spawn_execution_e2e(root: Path, project_id: str, template_id: str, run_id: str) -> None:
    run_payload = dev_pipeline_artifact_json(root, f"execution/runs/{run_id}.json") or dev_pipeline_artifact_json(root, "execution/execution_run.json")
    if str(run_payload.get("status") or "") != "running":
        return
    thread = threading.Thread(
        target=dev_pipeline_finish_execution_e2e,
        args=(root, project_id, template_id, run_id),
        name=f"dev-pipeline-delivery-{run_id}",
        daemon=True,
    )
    thread.start()


def dev_pipeline_start_default_issue_run(issue: dict[str, Any]) -> dict[str, Any]:
    root = DEV_PIPELINE_STUDIO_ROOT
    manifest_path = root / "pipeline_manifest.json"
    manifest = read_json_path(manifest_path)
    if not manifest:
        raise AgentWorkAppError(f"Dev Pipeline Studio manifest not found: {dev_pipeline_relative(manifest_path)}")
    if dev_pipeline_ensure_builtin_pipelines(manifest):
        write_json_path(manifest_path, manifest)
    projects = [item for item in manifest.get("projects", []) if isinstance(item, dict)]
    templates = [item for item in manifest.get("templates", []) if isinstance(item, dict)]
    project = dev_pipeline_find(projects, DEFAULT_DEV_PIPELINE_PROJECT_ID, DEFAULT_DEV_PIPELINE_PROJECT_ID)
    template = dev_pipeline_find(templates, DEFAULT_DEV_PIPELINE_TEMPLATE_ID, DEFAULT_DEV_PIPELINE_TEMPLATE_ID)
    if not project or not template:
        raise AgentWorkAppError("Default Dev Pipeline Studio route is unavailable")
    dev_pipeline_apply_generic_blueprint(template)
    issue_id = str(issue.get("id") or "")
    subject = str(issue.get("subject") or "")
    prompt = str(issue.get("description") or "")
    execution_run = dev_pipeline_seed_execution_e2e(
        root,
        manifest,
        project,
        template,
        {
            "triggered_by": f"issue-{issue_id}" if issue_id else "prompt-router",
            "issue_id": issue_id,
            "issue_subject": subject,
            "prompt": prompt,
            "message": f"Prompt issue #{issue_id} routed to Hard Proreq Project",
        },
    )

    defaults = manifest.get("defaults") if isinstance(manifest.get("defaults"), dict) else {}
    defaults["project_id"] = DEFAULT_DEV_PIPELINE_PROJECT_ID
    defaults["template_id"] = DEFAULT_DEV_PIPELINE_TEMPLATE_ID
    manifest["defaults"] = defaults
    manifest["active_run_id"] = str(execution_run.get("run_id") or "")
    manifest["status"] = str(execution_run.get("status") or "running")
    manifest["status_detail"] = f"Prompt issue #{issue_id} is routed to Hard Proreq Project"
    write_json_path(manifest_path, manifest)
    dev_pipeline_append_event(
        root,
        manifest,
        "pipeline_issue_prompt_routed",
        DEFAULT_DEV_PIPELINE_PROJECT_ID,
        DEFAULT_DEV_PIPELINE_TEMPLATE_ID,
        {
            "issue_id": issue_id,
            "issue_subject": subject,
            "execution_run_id": str(execution_run.get("run_id") or ""),
            "default_route": True,
        },
    )
    dev_pipeline_spawn_execution_e2e(root, DEFAULT_DEV_PIPELINE_PROJECT_ID, DEFAULT_DEV_PIPELINE_TEMPLATE_ID, str(execution_run.get("run_id") or ""))
    return {
        "project_id": DEFAULT_DEV_PIPELINE_PROJECT_ID,
        "template_id": DEFAULT_DEV_PIPELINE_TEMPLATE_ID,
        "run_id": str(execution_run.get("run_id") or ""),
        "status": str(execution_run.get("status") or "running"),
        "default": True,
        "url": "/dev-pipeline-studio#pipeline-flow",
    }


def dev_pipeline_execution_flow(
    root: Path,
    manifest: dict[str, Any],
    project: dict[str, Any],
    template: dict[str, Any],
    required_inputs: list[dict[str, Any]],
    workers: list[dict[str, Any]],
    integration_cards: list[dict[str, Any]],
    validator_cards: list[dict[str, Any]],
    evidence_cards: list[dict[str, Any]],
    event_total: int,
    budget_spent: float,
    budget_cap: float,
    selected_run_id: str = "",
) -> dict[str, Any]:
    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), dict) else {}
    events_rel = str(artifacts.get("events") or "events.ndjson")
    execution_manifest_rel = str(template.get("execution_manifest") or "execution/execution_manifest.json")
    execution_manifest = dev_pipeline_artifact_json(root, execution_manifest_rel)
    execution_run = dev_pipeline_artifact_json(root, "execution/execution_run.json")
    expected_pipeline = f"{template.get('id') or 'pipeline'}-{project.get('id') or 'project'}"
    if execution_manifest and execution_manifest.get("pipeline") and str(execution_manifest.get("pipeline") or "") != expected_pipeline:
        execution_manifest = {}
    if execution_run and str(execution_run.get("pipeline") or "") != expected_pipeline:
        execution_run = {}
        execution_manifest = {}
    current_run_id = str(execution_run.get("run_id") or execution_manifest.get("run_id") or "")
    selected_run_id = str(selected_run_id or "").strip()
    if selected_run_id and selected_run_id != current_run_id and "/" not in selected_run_id and "\\" not in selected_run_id:
        selected_run = dev_pipeline_artifact_json(root, f"execution/runs/{selected_run_id}.json")
        if selected_run and str(selected_run.get("pipeline") or "") == expected_pipeline:
            execution_run = selected_run
            current_run_id = str(execution_run.get("run_id") or "")
    elif not execution_run:
        for run in dev_pipeline_execution_history(root, "", expected_pipeline):
            selected_run = dev_pipeline_artifact_json(root, str(run.get("path") or ""))
            if selected_run and str(selected_run.get("pipeline") or "") == expected_pipeline:
                execution_run = selected_run
                current_run_id = str(execution_run.get("run_id") or "")
                break
    workset_receipt_rel = str(execution_run.get("workset_receipt") or "")
    workset_receipt = read_json_path(ROOT_DIR / workset_receipt_rel) if workset_receipt_rel else {}
    execution_steps = [item for item in execution_manifest.get("steps", []) if isinstance(item, dict)]
    if execution_run.get("steps"):
        execution_steps = [item for item in execution_run.get("steps", []) if isinstance(item, dict)]
    if not execution_steps:
        execution_steps = [
            {
                "id": str(item.get("id") or ""),
                "title": str(item.get("title") or item.get("id") or ""),
                "file": str(item.get("file") or ""),
                "status": str(item.get("status") or ""),
                "dependencies": [str(value) for value in item.get("dependencies", []) if isinstance(value, str)],
                "config": str(item.get("config") or ""),
                "receipt": str(item.get("receipt") or ""),
            }
            for item in template.get("factory_steps", [])
            if isinstance(item, dict)
        ]

    base_started = (
        parse_iso_datetime(execution_run.get("started_at"))
        or parse_iso_datetime(execution_manifest.get("run_started_at"))
        or parse_iso_datetime(manifest.get("run_started_at"))
        or parse_iso_datetime(execution_manifest.get("written_at"))
        or datetime.now(timezone.utc)
    )
    base_started = base_started.replace(microsecond=0)
    run_started = base_started if execution_run or execution_manifest.get("run_started_at") else base_started - timedelta(seconds=246)
    default_stage_durations = {
        "input": 31,
        "repo": 18,
        "blueprint": 24,
        "factory": max(72, len(execution_steps) * 9),
        "validation": 45,
        "handoff": 36,
    }
    step_defaults = [5, 6, 14, 8, 15, 18, 3, 3]
    factory_started = run_started + timedelta(seconds=90)
    step_rows: list[dict[str, Any]] = []
    cursor = factory_started
    for index, step in enumerate(execution_steps):
        status = dev_pipeline_execution_status_label(step.get("status"))
        duration = duration_seconds_from_label(step.get("duration"), step_defaults[index] if index < len(step_defaults) else 6)
        recorded_started_at = parse_iso_datetime(step.get("started_at"))
        recorded_finished_at = parse_iso_datetime(step.get("finished_at"))
        started_at = recorded_started_at or cursor
        planned_finished_at = started_at + timedelta(seconds=duration)
        finished_at = recorded_finished_at or planned_finished_at
        cursor = finished_at
        show_finished_at = recorded_finished_at
        show_started_at = started_at if recorded_started_at or (not execution_run and status != "queued") else None
        step_rows.append(
            {
                "id": str(step.get("id") or f"step-{index + 1}"),
                "title": str(step.get("title") or step.get("id") or f"step_{index + 1}"),
                "status": status,
                "duration_seconds": duration,
                "duration": duration_label(duration),
                "started": format_run_time(show_started_at, include_date=False),
                "finished": format_run_time(show_finished_at, include_date=False),
                "started_at": show_started_at.isoformat() if show_started_at else "",
                "finished_at": show_finished_at.isoformat() if show_finished_at else "",
                "file": str(step.get("file") or ""),
                "dependencies": [str(value) for value in step.get("dependencies", []) if isinstance(value, str)],
                "config": str(step.get("config") or ""),
                "receipt": str(step.get("receipt") or ""),
                "command": str(step.get("command") or ""),
                "exit_code": step.get("exit_code"),
            }
        )

    run_stage_overrides = {
        str(stage.get("id") or ""): stage
        for stage in execution_run.get("stages", [])
        if isinstance(stage, dict)
    }
    repo_workers = [{**item, "status": item.get("status") or "completed"} for item in workers if str(item.get("stage") or "repo") == "repo"]
    blueprint_workers = [{**item, "status": item.get("status") or "completed"} for item in workers if str(item.get("stage") or "") == "blueprint"]
    is_workset_delivery = str(execution_run.get("source") or execution_manifest.get("source") or "").startswith("cento-workset")
    is_proreq_light = str(template.get("id") or "") == PROREQ_LIGHT_TEMPLATE_ID or str(execution_run.get("source") or "").startswith("cento-proreq-light")
    is_hard_proreq = str(template.get("id") or "") == HARD_PROREQ_TEMPLATE_ID or is_proreq_light or str(execution_run.get("source") or "").startswith("cento-hard-proreq")
    is_multipipeline = str(template.get("id") or "") == MULTIPIPELINE_TEMPLATE_ID or str(execution_run.get("source") or "").startswith("cento-multipipeline")
    factory_title = "4. Sequential ProReq Chain" if is_multipipeline else ("4. ProReq Light Planning" if is_proreq_light else ("4. Proreq Planning" if is_hard_proreq else ("4. Workset Delivery" if is_workset_delivery else "4. Factory Execution")))
    stage_sources = [
        ("input", "1. Input Contract", required_inputs, "input", run_started),
        ("repo", "2. Repo Discovery", repo_workers, "repo", run_started + timedelta(seconds=55)),
        ("blueprint", "3. Change Blueprint", blueprint_workers, "blueprint", run_started + timedelta(seconds=73)),
        ("factory", factory_title, step_rows or integration_cards, "execution", factory_started),
        ("validation", "5. Deterministic Validation", validator_cards, "validation", cursor + timedelta(seconds=12)),
        ("handoff", "6. Evidence / Handoff", evidence_cards, "handoff", cursor + timedelta(seconds=57)),
    ]
    stages: list[dict[str, Any]] = []
    for index, (stage_id, title, items, log_key, started_at) in enumerate(stage_sources):
        override = run_stage_overrides.get(stage_id, {})
        started_at = parse_iso_datetime(override.get("started_at")) or started_at
        recorded_finished_at = parse_iso_datetime(override.get("finished_at"))
        finished_at = recorded_finished_at or started_at + timedelta(seconds=default_stage_durations[stage_id])
        duration_seconds = max(0, int(round((finished_at - started_at).total_seconds())))
        if not duration_seconds and stage_id not in {"handoff"} and not recorded_finished_at:
            duration_seconds = default_stage_durations[stage_id]
            finished_at = started_at + timedelta(seconds=duration_seconds)
        status = dev_pipeline_execution_stage_status(items)
        if override.get("status"):
            status = dev_pipeline_execution_status_label(override.get("status"))
        if not override.get("status") and stage_id in {"input", "factory", "validation", "handoff"} and items:
            status = "completed" if status != "failed" else status
        show_finished_at = recorded_finished_at if status not in {"running", "queued"} else None
        count_label = {
            "input": f"{len(items)} inputs ready",
            "repo": f"{len(items)} contract{'s' if len(items) != 1 else ''}",
            "blueprint": f"{len(items)} contract{'s' if len(items) != 1 else ''}",
            "factory": f"{len(step_rows)} steps",
            "validation": f"{len(items)} validators",
            "handoff": f"{len(items)} artifacts",
        }[stage_id]
        stages.append(
            {
                "id": stage_id,
                "index": index + 1,
                "title": title,
                "short_title": title.split(". ", 1)[-1],
                "status": status,
                "count": count_label,
                "duration_seconds": duration_seconds,
                "duration": duration_label(duration_seconds),
                "started": format_run_time(started_at, include_date=False),
                "finished": format_run_time(show_finished_at, include_date=False),
                "started_at": started_at.isoformat(),
                "finished_at": show_finished_at.isoformat() if show_finished_at else "",
                "log_key": log_key,
                "steps": step_rows if stage_id == "factory" else [],
            }
        )

    validation_passed = sum(1 for item in validator_cards if str(item.get("status") or "").lower() in {"passed", "completed"})
    all_items = [*required_inputs, *workers, *step_rows, *validator_cards, *evidence_cards]
    overall_status = dev_pipeline_execution_status_label(execution_run.get("status") or execution_manifest.get("status"))
    if overall_status == "configured":
        overall_status = "completed" if all_items and dev_pipeline_execution_stage_status(all_items) != "failed" else "configured"
    stage_finished = max((parse_iso_datetime(stage.get("finished_at")) or run_started for stage in stages), default=run_started)
    recorded_finished = parse_iso_datetime(execution_run.get("finished_at")) or parse_iso_datetime(execution_manifest.get("run_finished_at")) or stage_finished
    if overall_status in {"running", "queued"}:
        run_finished = datetime.now(timezone.utc)
    else:
        run_finished = max(stage_finished, recorded_finished)
    event_rows = read_event_rows(root / events_rel)
    logs: list[dict[str, Any]] = []
    for row in execution_run.get("logs", []):
        if not isinstance(row, dict):
            continue
        timestamp = parse_iso_datetime(row.get("timestamp")) or run_finished
        logs.append(
            {
                "time": format_run_time(timestamp, include_date=False),
                "stage": str(row.get("stage") or "execution"),
                "source": str(row.get("source") or "execution"),
                "message": str(row.get("message") or ""),
            }
        )
    for step in step_rows:
        timestamp = parse_iso_datetime(step.get("started_at")) or factory_started
        command_detail = f" via {step.get('command')}" if step.get("command") else ""
        step_status = str(step.get("status") or "configured")
        if step_status == "completed":
            message = f"{step['title']} completed with status {step_status}{command_detail}"
        elif step_status == "running":
            message = f"{step['title']} is running{command_detail}"
        else:
            message = f"{step['title']} is {step_status}{command_detail}"
        logs.append(
            {
                "time": format_run_time(timestamp, include_date=False),
                "stage": "execution",
                "source": step["id"],
                "message": message,
            }
        )
    workset_events_rel = str(execution_run.get("workset_events") or workset_receipt.get("events") or "")
    if workset_events_rel:
        for row in read_event_rows(ROOT_DIR / workset_events_rel, limit=60):
            timestamp = parse_iso_datetime(row.get("ts") or row.get("timestamp")) or run_finished
            event = str(row.get("event") or "workset_event").replace("_", " ")
            logs.append(
                {
                    "time": format_run_time(timestamp, include_date=False),
                    "stage": "execution",
                    "source": str(row.get("task_id") or row.get("workset_id") or "workset"),
                    "message": event,
                }
            )
    for row in event_rows[-24:]:
        timestamp = parse_iso_datetime(row.get("timestamp")) or run_finished
        event = str(row.get("event") or "pipeline_event").replace("pipeline_", "").replace("_", " ")
        details = row.get("details") if isinstance(row.get("details"), dict) else {}
        selected = details.get("selected_integration") or details.get("selected_validator") or details.get("selected_input") or details.get("selected_worker") or ""
        logs.append(
            {
                "time": format_run_time(timestamp, include_date=False),
                "stage": "pipeline",
                "source": str(selected or row.get("template_id") or "pipeline"),
                "message": event,
            }
        )
    logs.sort(key=lambda item: item.get("time", ""))

    summary_artifacts: list[dict[str, Any]] = []
    for artifact in execution_run.get("artifacts", []):
        if not isinstance(artifact, dict):
            continue
        path = str(artifact.get("path") or "").strip()
        if path and all(str(item.get("path") or "") != path for item in summary_artifacts):
            summary_artifacts.append(
                {
                    "name": str(artifact.get("name") or Path(path).name),
                    "path": path,
                    "size": str(artifact.get("size") or file_size_label(ROOT_DIR / path)),
                    "exists": bool(artifact.get("exists", (ROOT_DIR / path).exists())),
                }
            )
    if is_hard_proreq or is_multipipeline:
        fallback_artifacts = [
            execution_manifest_rel,
            f"execution/runs/{current_run_id}.json" if current_run_id else "execution/execution_run.json",
        ]
    else:
        fallback_artifacts = [
            str(artifacts.get("pipeline_receipt") or "evidence/pipeline_receipt.json"),
            str(artifacts.get("evidence_bundle") or "evidence/evidence_bundle.json"),
            execution_manifest_rel,
            f"execution/runs/{current_run_id}.json" if current_run_id else "execution/execution_run.json",
            str(artifacts.get("validation_receipt") or "validation/validation_receipt.json"),
            "evidence/handoff_packet.json",
        ]
    for rel in fallback_artifacts:
        clean = str(rel or "").strip()
        if not clean or any(str(item.get("path") or "") == clean for item in summary_artifacts):
            continue
        path = root / clean
        summary_artifacts.append(
            {
                "name": Path(clean).name,
                "path": clean,
                "size": file_size_label(path),
                "exists": path.exists(),
            }
        )

    manifest_active_run_id = str(manifest.get("active_run_id") or "")
    if manifest_active_run_id and not manifest_active_run_id.startswith(f"{expected_pipeline}-"):
        manifest_active_run_id = ""
    run_id = str(execution_run.get("run_id") or execution_manifest.get("run_id") or manifest_active_run_id or f"{expected_pipeline}-{run_started.strftime('%Y%m%dT%H%M%SZ')}")
    run_is_live = overall_status in {"running", "queued"}
    history = dev_pipeline_execution_history(root, current_run_id or run_id, expected_pipeline)
    if run_id and all(str(item.get("run_id") or "") != run_id for item in history):
        history.insert(
            0,
            {
                "run_id": run_id,
                "status": overall_status,
                "started": format_run_time(run_started),
                "finished": "In progress" if run_is_live else format_run_time(run_finished),
                "duration": duration_label(int((run_finished - run_started).total_seconds())),
                "source": str(execution_run.get("source") or execution_manifest.get("source") or "manifest-derived"),
                "pipeline": expected_pipeline,
                "active": run_id == (current_run_id or run_id),
                "path": dev_pipeline_relative(root / "execution" / "execution_run.json"),
                "artifact_count": len(summary_artifacts),
                "ready_artifact_count": len([item for item in summary_artifacts if bool(item.get("exists", True))]),
            },
        )
    return {
        "run_id": run_id,
        "active_run_id": current_run_id or run_id,
        "is_active_run": run_id == (current_run_id or run_id),
        "pipeline": expected_pipeline,
        "status": overall_status,
        "source": str(execution_run.get("source") or execution_manifest.get("source") or "manifest-derived"),
        "started": format_run_time(run_started),
        "finished": "In progress" if run_is_live else format_run_time(run_finished),
        "duration": duration_label(int((run_finished - run_started).total_seconds())),
        "triggered_by": str(execution_run.get("triggered_by") or manifest.get("triggered_by") or "jenkins-bot"),
        "run_mode": str(execution_run.get("apply_mode") or manifest.get("run_mode") or "Normal"),
        "evidence_policy": "Required",
        "manifest_version": str(manifest.get("version") or execution_manifest.get("schema_version") or "cento.execution_manifest.v1"),
        "event_count": event_total,
        "budget": f"${budget_spent:.2f} of ${budget_cap:.2f}",
        "stages": stages,
        "steps": step_rows,
        "selected_stage_id": "factory" if step_rows else (stages[0]["id"] if stages else ""),
        "logs": logs[-80:],
        "artifacts": summary_artifacts,
        "facts": [item for item in execution_run.get("facts", []) if isinstance(item, dict)],
        "readiness_errors": [str(item) for item in execution_run.get("readiness_errors", []) if isinstance(item, str)],
        "target_paths": [str(item) for item in execution_run.get("target_paths", []) if isinstance(item, str)],
        "changed_paths": [str(item) for item in execution_run.get("changed_paths", []) if isinstance(item, str)],
        "total_ai_cost_usd": execution_run.get("total_ai_cost_usd", workset_receipt.get("total_cost_usd") if workset_receipt else None),
        "workset_receipt": workset_receipt_rel,
        "parallel": dev_pipeline_execution_parallel_summary(execution_run, workset_receipt),
        "history": history,
        "validation_results": {
            "passed": validation_passed,
            "total": len(validator_cards),
            "items": [
                {
                    "id": str(item.get("id") or ""),
                    "title": str(item.get("title") or "Validator"),
                    "status": dev_pipeline_execution_status_label(item.get("status")),
                    "duration": duration_label(duration_seconds_from_label(item.get("duration"), 45 if index == 0 else 32 if index == 1 else 28)),
                }
                for index, item in enumerate(validator_cards)
            ],
        },
    }


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
    if dev_pipeline_ensure_builtin_pipelines(manifest):
        write_json_path(manifest_path, manifest)

    action = str(payload.get("action") or "save").strip() or "save"
    if action not in {"save", "select_worker", "duplicate", "new", "save_input", "save_validation", "run_validation", "save_integration", "save_evidence", "add_element", "delete_element", "run_execution_e2e", "run_delivery"}:
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

    execution_run: dict[str, Any] = {}
    if action in {"run_execution_e2e", "run_delivery"}:
        execution_run = dev_pipeline_seed_execution_e2e(root, manifest, project, template)

    defaults = manifest.get("defaults") if isinstance(manifest.get("defaults"), dict) else {}
    defaults["project_id"] = str(project.get("id") or "")
    defaults["template_id"] = str(template.get("id") or "")
    manifest["defaults"] = defaults
    manifest["active_run_id"] = f"{template.get('id')}-{project.get('id')}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    manifest["status"] = "configured" if action in {"save_input", "save_validation", "save_integration", "save_evidence", "add_element", "delete_element"} else "healthy"
    if action == "run_validation":
        manifest["status"] = str(config.get("status") or "configured") if "config" in locals() else "configured"
        manifest["status_detail"] = "Validation tab executed; validator receipts and run results are in sync"
    elif action in {"run_execution_e2e", "run_delivery"}:
        manifest["active_run_id"] = str(execution_run.get("run_id") or manifest.get("active_run_id") or "")
        manifest["status"] = str(execution_run.get("status") or "running")
        if str(template.get("id") or "") == HARD_PROREQ_TEMPLATE_ID:
            manifest["status_detail"] = "Hard proreq pipeline is generating Cento context, a muted UI screenshot request, GPT pro backend schema request, backend work, integration, validation, and evidence"
        elif str(template.get("id") or "") == MULTIPIPELINE_TEMPLATE_ID:
            manifest["status_detail"] = "Multipipeline ProReq chain is scheduling four sequential ProReq request passes, UI screenshot guidance, Pro request, roadmap, and evidence"
        elif manifest["status"] == "blocked":
            manifest["status_detail"] = "Workset delivery is blocked by readiness checks; execution_run.json lists the exact blocker"
        else:
            manifest["status_detail"] = "Workset delivery is running through cento workset execute with api-openai and direct worktree apply"
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
            "execution_run_id": str(execution_run.get("run_id") or ""),
        },
    )
    if action in {"run_execution_e2e", "run_delivery"} and execution_run.get("run_id") and str(execution_run.get("status") or "") == "running":
        dev_pipeline_spawn_execution_e2e(root, str(project.get("id") or ""), str(template.get("id") or ""), str(execution_run.get("run_id") or ""))
    state = dev_pipeline_studio_state(project_id=str(project.get("id") or ""), template_id=str(template.get("id") or ""))
    if mutation:
        state["mutation"] = mutation
    return state


def dev_pipeline_studio_state(project_id: str = "", template_id: str = "", run_id: str = "") -> dict[str, Any]:
    root = DEV_PIPELINE_STUDIO_ROOT
    manifest_path = root / "pipeline_manifest.json"
    manifest = read_json_path(manifest_path)
    if not manifest:
        raise AgentWorkAppError(f"Dev Pipeline Studio manifest not found: {dev_pipeline_relative(manifest_path)}")
    if dev_pipeline_ensure_builtin_pipelines(manifest):
        write_json_path(manifest_path, manifest)

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
                "max_parallel": int(item.get("max_parallel", 1) or 1),
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
            "execution_flow": dev_pipeline_execution_flow(
                root,
                manifest,
                project,
                template,
                required_inputs,
                workers,
                integration_cards,
                validator_cards,
                evidence_cards,
                event_total,
                budget_spent,
                budget_cap,
                run_id,
            ),
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
    custom_fields = issue_custom_fields_for_issue(conn, issue_id)
    pipeline_run_id = str(custom_fields.get("Default Pipeline Run") or "").strip()
    pipeline_route = None
    if pipeline_run_id:
        pipeline_route = {
            "default": True,
            "project_id": str(custom_fields.get("Pipeline Project") or DEFAULT_DEV_PIPELINE_PROJECT_ID),
            "template_id": str(custom_fields.get("Pipeline Template") or DEFAULT_DEV_PIPELINE_TEMPLATE_ID),
            "run_id": pipeline_run_id,
            "status": "routed",
            "url": "/dev-pipeline-studio#pipeline-flow",
        }
    return {
        "issue": issue_payload,
        "journals": journals,
        "attachments": attachments,
        "custom_fields": custom_fields,
        "validation_evidences": issue_validation_evidences(conn, issue_id),
        **({"pipeline_route": pipeline_route} if pipeline_route else {}),
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


def latest_demo_video_path() -> str:
    demo_root = ROOT_DIR / "workspace" / "runs" / "demo-evidence"
    candidates: list[tuple[float, Path]] = []
    for receipt_path in demo_root.glob("*/receipt.json"):
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if str(receipt.get("status") or "").lower() not in {"passed", "ok"}:
            continue
        if str(receipt.get("recorder") or "").lower() == "synthetic":
            continue
        artifacts = receipt.get("artifacts")
        video_ref = ""
        if isinstance(artifacts, dict):
            video_ref = str(artifacts.get("video") or "")
        video_path = Path(video_ref) if video_ref else receipt_path.parent / "demo.mp4"
        if not video_path.is_absolute():
            video_path = ROOT_DIR / video_path
        video_path = video_path.resolve()
        if ROOT_DIR.resolve() not in video_path.parents and video_path != ROOT_DIR.resolve():
            continue
        if not video_path.exists() or not video_path.is_file() or video_path.suffix.lower() not in {".mp4", ".webm", ".mov"}:
            fallback_video = receipt_path.parent / "demo.mp4"
            if not fallback_video.exists() or not fallback_video.is_file():
                continue
            video_path = fallback_video.resolve()
        try:
            sort_time = max(receipt_path.stat().st_mtime, video_path.stat().st_mtime)
        except OSError:
            continue
        candidates.append((sort_time, video_path))
    if not candidates:
        raise AgentWorkAppError("No recorded demo evidence video found.")
    return str(max(candidates, key=lambda item: item[0])[1].relative_to(ROOT_DIR))


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
    detail = issue_detail(conn, issue_id)
    return detail


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


PATCH_SWARM_PRODUCT_WORKTREE_ROOT = ROOT_DIR / "workspace" / "runs" / "patch-swarm-product-worktrees"
PATCH_SWARM_PROTECTED_PREFIXES = (".git/", ".ssh/", ".gnupg/", ".oci/")
PATCH_SWARM_PROTECTED_NAMES = {".env", ".env.mcp", "secrets.env", "id_rsa", "id_ed25519"}
PATCH_SWARM_PROTECTED_SUFFIXES = (".pem", ".key", ".p12", ".pfx")


def patch_swarm_engine():
    import parallel_delivery as patch_swarm  # local import avoids a module-import cycle

    return patch_swarm


def patch_swarm_console_tool():
    import parallel_delivery_patch_swarm_console as console_tool

    return console_tool


def patch_swarm_git(repo: Path, *args: str, timeout: int = 20) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)


def patch_swarm_repo_search_roots() -> list[Path]:
    raw = os.environ.get("CENTO_PATCH_SWARM_REPO_ROOTS", "")
    roots = [Path(item).expanduser() for item in raw.split(os.pathsep) if item.strip()] if raw else [ROOT_DIR, Path.home() / "projects"]
    unique: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        resolved = root.resolve() if root.exists() else root
        if resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)
    return unique


def patch_swarm_protected_path(path: str) -> bool:
    normalized = str(path or "").strip().lstrip("/")
    name = Path(normalized).name
    lowered = normalized.lower()
    return (
        name in PATCH_SWARM_PROTECTED_NAMES
        or lowered.startswith(PATCH_SWARM_PROTECTED_PREFIXES)
        or lowered.endswith(PATCH_SWARM_PROTECTED_SUFFIXES)
        or "/.env" in lowered
        or "secret" in lowered
    )


def patch_swarm_status_path(line: str) -> str:
    raw = line[3:] if len(line) > 3 else line
    if " -> " in raw:
        raw = raw.rsplit(" -> ", 1)[-1]
    return raw.strip()


def patch_swarm_repo_state(repo: Path) -> dict[str, Any]:
    repo = repo.expanduser().resolve()
    top = patch_swarm_git(repo, "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        raise AgentWorkAppError(f"not a git repository: {repo}")
    root = Path(top.stdout.strip()).resolve()
    branch_result = patch_swarm_git(root, "rev-parse", "--abbrev-ref", "HEAD")
    sha_result = patch_swarm_git(root, "rev-parse", "--short", "HEAD")
    status_result = patch_swarm_git(root, "status", "--porcelain=v1")
    status_lines = [line for line in status_result.stdout.splitlines() if line.strip()]
    dirty_paths = [patch_swarm_status_path(line) for line in status_lines]
    protected_dirty = [path for path in dirty_paths if patch_swarm_protected_path(path)]
    return {
        "path": str(root),
        "name": root.name,
        "branch": branch_result.stdout.strip() if branch_result.returncode == 0 else "unknown",
        "head": sha_result.stdout.strip() if sha_result.returncode == 0 else "",
        "dirty": bool(status_lines),
        "dirty_count": len(status_lines),
        "dirty_paths": dirty_paths[:50],
        "protected_dirty": protected_dirty[:50],
        "protected_dirty_count": len(protected_dirty),
        "can_start": not protected_dirty,
        "can_apply_without_override": not status_lines,
    }


def patch_swarm_discover_repos() -> dict[str, Any]:
    repos: dict[str, dict[str, Any]] = {}
    for root in patch_swarm_repo_search_roots():
        if not root.exists() or not root.is_dir():
            continue
        candidates = [root]
        try:
            candidates.extend(path for path in root.iterdir() if path.is_dir() and not path.name.startswith("."))
        except OSError:
            continue
        for candidate in candidates:
            if not (candidate / ".git").exists():
                continue
            try:
                state = patch_swarm_repo_state(candidate)
            except (AgentWorkAppError, OSError, subprocess.SubprocessError):
                continue
            repos[state["path"]] = state
    ordered = sorted(repos.values(), key=lambda item: (item["name"].lower(), item["path"]))
    return {
        "schema_version": "cento.patch_swarm.repo_index.v1",
        "repos": ordered,
        "search_roots": [str(path) for path in patch_swarm_repo_search_roots()],
        "protected_policy": {
            "names": sorted(PATCH_SWARM_PROTECTED_NAMES),
            "suffixes": list(PATCH_SWARM_PROTECTED_SUFFIXES),
            "prefixes": list(PATCH_SWARM_PROTECTED_PREFIXES),
        },
    }


def patch_swarm_detect_test_commands(repo: Path) -> list[str]:
    commands: list[str] = []
    if (repo / "package.json").exists():
        commands.append("npm test")
    if (repo / "pyproject.toml").exists() or (repo / "pytest.ini").exists() or (repo / "tests").exists():
        commands.append("python3 -m pytest")
    if (repo / "go.mod").exists():
        commands.append("go test ./...")
    if (repo / "Cargo.toml").exists():
        commands.append("cargo test")
    if (repo / "Makefile").exists():
        commands.append("make test")
    return commands


def patch_swarm_run_path(run_id: str) -> Path:
    return patch_swarm_engine().resolve_patch_swarm_run_dir(run_id)


def patch_swarm_console_run_dir(run_id: str = "", raw_run_dir: str = "") -> Path:
    tool = patch_swarm_console_tool()
    if raw_run_dir:
        run_dir = tool.normalize_run_dir(Path(raw_run_dir))
    elif run_id:
        run_dir = patch_swarm_run_path(run_id)
    else:
        run_dir = tool.normalize_run_dir(tool.RUNS_ROOT)
    workspace_root = (ROOT_DIR / "workspace" / "runs").resolve()
    if workspace_root not in run_dir.parents and run_dir != workspace_root:
        raise AgentWorkAppError("Patch Swarm console run_dir must be under workspace/runs.")
    return run_dir


def patch_swarm_console_render(run_id: str = "", raw_run_dir: str = "") -> tuple[dict[str, Any], Path]:
    tool = patch_swarm_console_tool()
    run_dir = patch_swarm_console_run_dir(run_id=run_id, raw_run_dir=raw_run_dir)
    console_data, metadata = tool.render_console(run_dir, write_html=True)
    html_path = (ROOT_DIR / metadata["start_here"]).resolve()
    payload = tool.console_data_to_dict(console_data)
    payload["artifacts"] = metadata
    return payload, html_path


def patch_swarm_append_product_event(run_dir: Path, event: str, payload: dict[str, Any]) -> None:
    row = {"written_at": datetime.now(timezone.utc).isoformat(), "event": event, **payload}
    path = run_dir / "product_events.ndjson"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def patch_swarm_product_history(run_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in (run_dir / "events.ndjson", run_dir / "product_events.ndjson"):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines[-80:]:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return sorted(rows, key=lambda item: str(item.get("written_at") or ""))[-120:]


def patch_swarm_product_owned_path(run_id: str, execution_id: str) -> str:
    clean_run = re.sub(r"[^A-Za-z0-9_.-]+", "-", run_id).strip("-") or "run"
    clean_execution = re.sub(r"[^A-Za-z0-9_.-]+", "-", execution_id).strip("-") or "execution"
    return f"patch-swarm-candidates/{clean_run}/{clean_execution}.md"


def patch_swarm_retarget_run_to_repo(run_dir: Path, repo: Path, task_brief: str) -> None:
    engine = patch_swarm_engine()
    manifest = engine.read_json(run_dir / "patch_swarm_manifest.json")
    proreq = engine.read_json(run_dir / "proreq_execution_manifest.json")
    providers = engine.patch_swarm_provider_list(manifest.get("providers") if isinstance(manifest.get("providers"), list) else "")
    executions = [item for item in proreq.get("executions", []) if isinstance(item, dict)]
    for execution in executions:
        execution_id = str(execution.get("id") or "execution")
        owned_path = patch_swarm_product_owned_path(run_dir.name, execution_id)
        execution["owned_paths"] = [owned_path]
        execution_dir = run_dir / "proreq_executions" / execution_id
        request_path = execution_dir / "proreq_request.json"
        request = engine.read_json(request_path)
        if request:
            request["owned_paths"] = [owned_path]
            request["selected_repo"] = str(repo)
            request["task_brief"] = task_brief
            engine.write_json(request_path, request)
        (execution_dir / "prompt.md").write_text(
            engine.patch_swarm_prompt_text(task_brief, execution, providers, int(execution.get("candidate_target") or 1)),
            encoding="utf-8",
        )
    proreq["executions"] = executions
    proreq["selected_repo"] = str(repo)
    engine.write_json(run_dir / "proreq_execution_manifest.json", proreq)


def patch_swarm_write_product_metadata(run_dir: Path, metadata: dict[str, Any]) -> dict[str, Any]:
    engine = patch_swarm_engine()
    metadata = {
        "schema_version": "cento.patch_swarm.product_metadata.v1",
        "run_id": run_dir.name,
        "written_at": datetime.now(timezone.utc).isoformat(),
        **metadata,
    }
    engine.write_json(run_dir / "product_metadata.json", metadata)
    manifest = engine.read_json(run_dir / "patch_swarm_manifest.json")
    manifest["product_metadata"] = engine.rel(run_dir / "product_metadata.json")
    manifest["selected_repo"] = metadata.get("selected_repo", {})
    manifest["task_brief"] = metadata.get("task_brief", "")
    manifest["validation_profile"] = metadata.get("validation_profile", "deterministic")
    manifest["provider_preset"] = metadata.get("provider_preset", "balanced")
    engine.write_json(run_dir / "patch_swarm_manifest.json", manifest)
    engine.patch_swarm_write_ui_state(run_dir)
    return metadata


def patch_swarm_product_candidates(run_dir: Path) -> list[dict[str, Any]]:
    engine = patch_swarm_engine()
    index = engine.read_json(run_dir / "candidate_index.json")
    candidates = [dict(item) for item in index.get("candidates", []) if isinstance(item, dict)]
    decisions = engine.read_json(run_dir / "candidate_decisions.json")
    rejected = {str(item.get("candidate_id") or ""): item for item in decisions.get("rejected", []) if isinstance(item, dict)}
    for candidate in candidates:
        candidate_id = str(candidate.get("id") or "")
        patch_file = str((candidate.get("patch") or {}).get("patch_file") or "")
        diff_preview = ""
        if patch_file:
            patch_path = engine.resolve_cento_path(patch_file)
            try:
                diff_preview = patch_path.read_text(encoding="utf-8", errors="ignore")[:8000]
            except OSError:
                diff_preview = ""
        candidate["diff_preview"] = diff_preview
        candidate["decision"] = "rejected" if candidate_id in rejected else ""
        candidate["confidence"] = max(0, min(100, int(round(float(candidate.get("score") or 0)))))
    return candidates


def patch_swarm_product_run_detail(run_id: str, *, include_candidates: bool = True) -> dict[str, Any]:
    engine = patch_swarm_engine()
    run_dir = patch_swarm_run_path(run_id)
    manifest = engine.read_json(run_dir / "patch_swarm_manifest.json")
    if not manifest:
        raise AgentWorkAppError(f"Patch Swarm run not found: {run_id}")
    ui_state = engine.read_json(run_dir / "ui_state.json")
    receipt = engine.read_json(run_dir / "patch_swarm_receipt.json")
    integration = engine.read_json(run_dir / "integration_execution" / "integration_execution.json")
    validation = engine.read_json(run_dir / "validation_summary.json")
    approval = engine.read_json(run_dir / "supervised_approval.json")
    apply_receipt = engine.read_json(run_dir / "product_safe_integrator_apply.json")
    factory_promotion = engine.read_json(run_dir / "factory_promotion.json")
    metadata = engine.read_json(run_dir / "product_metadata.json")
    selected_repo = metadata.get("selected_repo") if isinstance(metadata.get("selected_repo"), dict) else manifest.get("selected_repo", {})
    candidates = patch_swarm_product_candidates(run_dir) if include_candidates else []
    groups: dict[str, list[dict[str, Any]]] = {}
    for candidate in candidates:
        groups.setdefault(str(candidate.get("execution_id") or "unknown"), []).append(candidate)
    run = {
        "run_id": run_dir.name,
        "run_dir": engine.rel(run_dir),
        "status": ui_state.get("status") or validation.get("status") or integration.get("status") or receipt.get("status") or manifest.get("status", "unknown"),
        "task_brief": metadata.get("task_brief") or manifest.get("objective", ""),
        "selected_repo": selected_repo,
        "candidate_target": manifest.get("candidate_target", 0),
        "candidate_count": receipt.get("candidate_count", 0),
        "selected_count": integration.get("selected_count", 0),
        "estimated_cost_usd": receipt.get("estimated_cost_usd", 0.0),
        "providers": manifest.get("providers", []),
        "validation": validation.get("status", "unknown"),
        "safe_integrator_status": (engine.read_json(run_dir / "safe_integrator_handoff.json")).get("status", ""),
        "approval_status": approval.get("status", "not_approved"),
        "apply_status": apply_receipt.get("status") or factory_promotion.get("status") or "not_applied",
        "created_at": manifest.get("created_at", ""),
        "updated_at": manifest.get("updated_at", ""),
        "artifacts": ui_state.get("artifacts", {}),
    }
    return {
        "schema_version": "cento.patch_swarm.product_run_detail.v1",
        "run": run,
        "ui_state": ui_state,
        "metadata": metadata,
        "receipt": receipt,
        "integration": integration,
        "validation_summary": validation,
        "approval": approval,
        "apply_receipt": apply_receipt,
        "factory_promotion": factory_promotion,
        "candidates": candidates,
        "candidate_groups": [{"execution_id": key, "candidates": value} for key, value in groups.items()],
        "history": patch_swarm_product_history(run_dir),
    }


def patch_swarm_product_run_list() -> dict[str, Any]:
    engine = patch_swarm_engine()
    root = engine.PATCH_SWARM_RUNS_ROOT
    runs: list[dict[str, Any]] = []
    if root.exists():
        for run_dir in sorted(root.iterdir(), key=lambda path: path.stat().st_mtime, reverse=True):
            if not run_dir.is_dir() or not (run_dir / "patch_swarm_manifest.json").exists():
                continue
            runs.append(patch_swarm_product_run_detail(run_dir.name, include_candidates=False)["run"])
    return {
        "schema_version": "cento.patch_swarm.run_index.v1",
        "runs": runs[:50],
        "summary": {
            "total": len(runs),
            "approved": sum(1 for item in runs if item.get("approval_status") == "approved"),
            "applied": sum(1 for item in runs if item.get("apply_status") == "applied"),
        },
    }


def patch_swarm_product_create_run(payload: dict[str, Any]) -> dict[str, Any]:
    engine = patch_swarm_engine()
    repo_path = str(payload.get("repo_path") or payload.get("repo") or "").strip()
    if not repo_path:
        raise AgentWorkAppError("repo_path is required")
    repo_state = patch_swarm_repo_state(Path(repo_path))
    if repo_state.get("protected_dirty"):
        raise AgentWorkAppError("selected repo has protected dirty paths: " + ", ".join(repo_state["protected_dirty"][:5]))
    task_brief = str(payload.get("task_brief") or payload.get("objective") or "").strip()
    if not task_brief:
        raise AgentWorkAppError("task_brief is required")
    run_id = str(payload.get("run_id") or f"patch-swarm-product-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
    run_dir = engine.resolve_patch_swarm_run_dir(run_id, create=True)
    candidate_target = max(10, int(payload.get("candidate_target") or 30))
    max_parallel_agents = max(1, int(payload.get("max_parallel_agents") or 3))
    providers = engine.patch_swarm_provider_list(payload.get("providers") or "codex-exec,claude-code,api-openai")
    mode = str(payload.get("mode") or "fixture").lower()
    live = mode in {"live", "real"}
    engine.build_patch_swarm_plan(run_dir, objective=task_brief, candidate_target=candidate_target, max_parallel_agents=max_parallel_agents, providers=providers, live=live)
    repo = Path(repo_state["path"])
    patch_swarm_retarget_run_to_repo(run_dir, repo, task_brief)
    patch_swarm_write_product_metadata(
        run_dir,
        {
            "selected_repo": repo_state,
            "task_brief": task_brief,
            "validation_profile": str(payload.get("validation_profile") or "deterministic"),
            "provider_preset": str(payload.get("provider_preset") or "balanced"),
            "test_commands": patch_swarm_detect_test_commands(repo),
            "ui_state": {"active_candidate_id": "", "compare_candidate_ids": [], "filters": {}},
            "apply_policy": "supervised-safe-integrator-worktree",
        },
    )
    receipt = engine.execute_patch_swarm(
        run_dir,
        fixture=not live,
        budget_cap_usd=payload.get("budget_cap_usd"),
        max_budget_usd=payload.get("max_budget_usd"),
        api_sandbox_candidates=int(payload.get("api_sandbox_candidates") or 1),
    )
    if receipt.get("status") == "candidates_generated":
        engine.integrate_patch_swarm(run_dir)
        engine.validate_patch_swarm_run(run_dir)
    engine.patch_swarm_write_ui_state(run_dir)
    patch_swarm_append_product_event(run_dir, "product_run_created", {"repo": repo_state["path"], "candidate_target": candidate_target, "mode": mode})
    return patch_swarm_product_run_detail(run_dir.name)


def patch_swarm_product_selected_candidates(run_dir: Path, candidate_ids: list[str] | None = None) -> list[dict[str, Any]]:
    candidates = patch_swarm_product_candidates(run_dir)
    by_id = {str(item.get("id") or ""): item for item in candidates}
    selected_ids = [str(item) for item in candidate_ids or [] if str(item)]
    if not selected_ids:
        integration = patch_swarm_engine().read_json(run_dir / "integration_execution" / "integration_execution.json")
        selected_ids = [str(item) for item in integration.get("selected_candidates", []) if str(item)]
    selected = [by_id[item] for item in selected_ids if item in by_id]
    if not selected:
        raise AgentWorkAppError("no selected candidates are available for approval")
    invalid = [str(item.get("id") or "") for item in selected if str(item.get("status") or "") != "validated"]
    if invalid:
        raise AgentWorkAppError("approval requires validated candidates: " + ", ".join(invalid))
    return selected


def patch_swarm_product_approve(run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    engine = patch_swarm_engine()
    run_dir = patch_swarm_run_path(run_id)
    selected = patch_swarm_product_selected_candidates(run_dir, payload.get("candidate_ids") if isinstance(payload.get("candidate_ids"), list) else None)
    approval = {
        "schema_version": "cento.patch_swarm.supervised_approval.v1",
        "run_id": run_dir.name,
        "status": "approved",
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "approved_by": str(payload.get("approved_by") or "local-operator"),
        "notes": str(payload.get("notes") or ""),
        "selected_candidate_ids": [str(item.get("id") or "") for item in selected],
        "selected_count": len(selected),
        "apply_policy": "Factory/Safe Integrator worktree only; no direct selected-repo mutation",
    }
    engine.write_json(run_dir / "supervised_approval.json", approval)
    engine.patch_swarm_write_ui_state(run_dir)
    patch_swarm_append_product_event(run_dir, "product_run_approved", {"selected_count": len(selected)})
    return patch_swarm_product_run_detail(run_dir.name)


def patch_swarm_product_reject(run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    engine = patch_swarm_engine()
    run_dir = patch_swarm_run_path(run_id)
    candidate_ids = [str(item) for item in payload.get("candidate_ids", []) if str(item)] if isinstance(payload.get("candidate_ids"), list) else []
    if not candidate_ids:
        raise AgentWorkAppError("candidate_ids is required")
    decisions = engine.read_json(run_dir / "candidate_decisions.json")
    existing = [item for item in decisions.get("rejected", []) if isinstance(item, dict) and str(item.get("candidate_id") or "") not in set(candidate_ids)]
    for candidate_id in candidate_ids:
        existing.append(
            {
                "candidate_id": candidate_id,
                "decision": "rejected",
                "reason": str(payload.get("reason") or "Rejected in Patch Swarm review."),
                "decided_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    engine.write_json(
        run_dir / "candidate_decisions.json",
        {
            "schema_version": "cento.patch_swarm.candidate_decisions.v1",
            "run_id": run_dir.name,
            "rejected": existing,
            "written_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    engine.patch_swarm_write_ui_state(run_dir)
    patch_swarm_append_product_event(run_dir, "product_candidates_rejected", {"candidate_ids": candidate_ids})
    return patch_swarm_product_run_detail(run_dir.name)


def patch_swarm_remove_product_worktree(path: Path, repo: Path) -> None:
    if not path.exists():
        return
    root = PATCH_SWARM_PRODUCT_WORKTREE_ROOT.resolve()
    resolved = path.resolve()
    if root not in resolved.parents and resolved != root:
        raise AgentWorkAppError(f"refusing to remove non-product worktree: {path}")
    patch_swarm_git(repo, "worktree", "remove", "--force", str(resolved), timeout=60)


def patch_swarm_product_external_apply(run_dir: Path, selected: list[dict[str, Any]], payload: dict[str, Any]) -> dict[str, Any]:
    engine = patch_swarm_engine()
    metadata = engine.read_json(run_dir / "product_metadata.json")
    repo_info = metadata.get("selected_repo") if isinstance(metadata.get("selected_repo"), dict) else {}
    repo = Path(str(repo_info.get("path") or "")).expanduser().resolve()
    if not repo.exists():
        raise AgentWorkAppError("selected repo is unavailable")
    branch = str(payload.get("branch") or f"patch-swarm/{run_dir.name}")
    worktree = Path(str(payload.get("worktree") or PATCH_SWARM_PRODUCT_WORKTREE_ROOT / run_dir.name)).expanduser()
    if not worktree.is_absolute():
        worktree = ROOT_DIR / worktree
    product_root = PATCH_SWARM_PRODUCT_WORKTREE_ROOT.resolve()
    resolved_worktree = worktree.resolve()
    if product_root not in resolved_worktree.parents and resolved_worktree != product_root:
        raise AgentWorkAppError(f"refusing non-product Patch Swarm worktree: {worktree}")
    patch_swarm_remove_product_worktree(worktree, repo)
    worktree.parent.mkdir(parents=True, exist_ok=True)
    add_result = patch_swarm_git(repo, "worktree", "add", "-f", "-B", branch, str(worktree), "HEAD", timeout=120)
    applied: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    if add_result.returncode == 0:
        limit = int(payload.get("limit") or 0)
        candidates = selected[:limit] if limit > 0 else selected
        for candidate in candidates:
            patch_file = str((candidate.get("patch") or {}).get("patch_file") or "")
            patch_path = engine.resolve_cento_path(patch_file)
            check = patch_swarm_git(worktree, "apply", "--check", str(patch_path), timeout=60)
            if check.returncode != 0:
                rejected.append({"candidate_id": candidate.get("id"), "reason": "git apply check failed", "stderr_tail": check.stderr[-1000:]})
                continue
            apply_result = patch_swarm_git(worktree, "apply", str(patch_path), timeout=60)
            if apply_result.returncode == 0:
                applied.append({"candidate_id": candidate.get("id"), "patch_file": patch_file, "touched_paths": candidate.get("touched_paths", [])})
            else:
                rejected.append({"candidate_id": candidate.get("id"), "reason": "git apply failed", "stderr_tail": apply_result.stderr[-1000:]})
    receipt = {
        "schema_version": "cento.patch_swarm.external_safe_integrator_apply.v1",
        "run_id": run_dir.name,
        "status": "applied" if add_result.returncode == 0 and applied and not rejected else "apply_blocked",
        "selected_repo": str(repo),
        "branch": branch,
        "worktree": str(worktree),
        "worktree_add": {
            "exit_code": add_result.returncode,
            "stdout_tail": add_result.stdout[-1000:],
            "stderr_tail": add_result.stderr[-1000:],
        },
        "applied": applied,
        "rejected": rejected,
        "applied_count": len(applied),
        "rejected_count": len(rejected),
        "written_at": datetime.now(timezone.utc).isoformat(),
    }
    engine.write_json(run_dir / "product_safe_integrator_apply.json", receipt)
    engine.patch_swarm_write_ui_state(run_dir)
    patch_swarm_append_product_event(run_dir, "product_safe_integrator_apply", {"status": receipt["status"], "applied_count": len(applied), "rejected_count": len(rejected)})
    return receipt


def patch_swarm_product_apply(run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    engine = patch_swarm_engine()
    run_dir = patch_swarm_run_path(run_id)
    approval = engine.read_json(run_dir / "supervised_approval.json")
    if approval.get("status") != "approved":
        raise AgentWorkAppError("apply requires supervised approval")
    selected_ids = [str(item) for item in approval.get("selected_candidate_ids", []) if str(item)]
    selected = patch_swarm_product_selected_candidates(run_dir, selected_ids)
    repo_root = engine.patch_swarm_selected_repo_root(run_dir).resolve()
    if repo_root == ROOT_DIR.resolve() and bool(payload.get("use_factory", True)):
        promotion = engine.promote_patch_swarm_to_factory(
            run_dir,
            selected,
            factory_run=str(payload.get("factory_run") or ""),
            apply=True,
            validate_each=bool(payload.get("validate_each", False)),
            branch=str(payload.get("branch") or ""),
            worktree=str(payload.get("worktree") or ""),
            limit=int(payload.get("limit") or 0),
        )
        engine.patch_swarm_write_ui_state(run_dir)
        patch_swarm_append_product_event(run_dir, "product_factory_apply", {"status": promotion.get("status"), "selected_count": len(selected)})
    else:
        patch_swarm_product_external_apply(run_dir, selected, payload)
    return patch_swarm_product_run_detail(run_dir.name)


def safe_static_path(raw_path: str) -> Path:
    route = raw_path.split("?", 1)[0].split("#", 1)[0]
    app_routes = {
        "/",
        "/review",
        "/cluster",
        "/consulting",
        "/factory",
        "/patch-swarm",
        "/docs",
        "/research-center",
        "/software-delivery-hub",
        "/dev-pipeline-studio",
        "/codebase-intelligence",
        "/issues",
        "/issues/new",
    }
    if route in ("",) or route in app_routes or route.startswith("/issues/") or route.startswith("/patch-swarm/runs/"):
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
                if parsed.path == "/patch-swarm/console" or (parsed.path.startswith("/patch-swarm/runs/") and parsed.path.endswith("/console")):
                    query = parse_qs(parsed.query)
                    raw_run_dir = str((query.get("run_dir") or [""])[0])
                    run_id = ""
                    parts = [part for part in parsed.path.split("/") if part]
                    if len(parts) == 4 and parts[0] == "patch-swarm" and parts[1] == "runs" and parts[3] == "console":
                        run_id = parts[2]
                    _payload, html_path = patch_swarm_console_render(run_id=run_id, raw_run_dir=raw_run_dir)
                    body = html_path.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
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
                if parsed.path == "/api/patch-swarm/repos":
                    self.send_json(200, patch_swarm_discover_repos())
                    return
                if parsed.path == "/api/patch-swarm/runs":
                    self.send_json(200, patch_swarm_product_run_list())
                    return
                if parsed.path == "/api/patch-swarm/console":
                    query = parse_qs(parsed.query)
                    raw_run_dir = str((query.get("run_dir") or [""])[0])
                    payload, _html_path = patch_swarm_console_render(raw_run_dir=raw_run_dir)
                    self.send_json(200, payload)
                    return
                if parsed.path.startswith("/api/patch-swarm/runs/"):
                    parts = [part for part in parsed.path.split("/") if part]
                    if len(parts) == 5 and parts[4] == "console":
                        query = parse_qs(parsed.query)
                        raw_run_dir = str((query.get("run_dir") or [""])[0])
                        payload, _html_path = patch_swarm_console_render(run_id=parts[3], raw_run_dir=raw_run_dir)
                        self.send_json(200, payload)
                        return
                    if len(parts) == 4:
                        self.send_json(200, patch_swarm_product_run_detail(parts[3]))
                        return
                if parsed.path == "/api/dev-pipeline-studio":
                    query = parse_qs(parsed.query)
                    project_id = str((query.get("project") or [""])[0])
                    template_id = str((query.get("template") or [""])[0])
                    run_id = str((query.get("run_id") or [""])[0])
                    self.send_json(200, dev_pipeline_studio_state(project_id=project_id, template_id=template_id, run_id=run_id))
                    return
                if parsed.path == "/api/demo-evidence/latest":
                    try:
                        latest_demo = latest_demo_video_path()
                    except AgentWorkAppError as exc:
                        self.send_json(404, {"error": str(exc)})
                        return
                    self.send_response(302)
                    self.send_header("Location", artifact_url(latest_demo))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
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
            except AgentWorkAppError as exc:
                self.send_json(400, {"error": str(exc)})
            except Exception as exc:
                self.send_json(500, {"error": str(exc)})

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            try:
                payload = self.read_json()
                if parsed.path == "/api/dev-pipeline-studio":
                    self.send_json(200, dev_pipeline_update(payload))
                    return
                if parsed.path == "/api/patch-swarm/runs":
                    self.send_json(201, patch_swarm_product_create_run(payload))
                    return
                if parsed.path.startswith("/api/patch-swarm/runs/"):
                    parts = [part for part in parsed.path.split("/") if part]
                    if len(parts) == 5 and parts[4] in {"approve", "reject", "apply"}:
                        if parts[4] == "approve":
                            self.send_json(200, patch_swarm_product_approve(parts[3], payload))
                            return
                        if parts[4] == "reject":
                            self.send_json(200, patch_swarm_product_reject(parts[3], payload))
                            return
                        self.send_json(200, patch_swarm_product_apply(parts[3], payload))
                        return
                if parsed.path == "/api/pipeline-runs":
                    self.send_json(201, dev_pipeline_start_pipeline_run(payload))
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
            except AgentWorkAppError as exc:
                self.send_json(400, {"error": str(exc)})
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
