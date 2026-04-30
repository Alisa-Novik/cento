#!/usr/bin/env python3

from __future__ import annotations

import argparse
import base64
import hashlib
import json
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


ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "cento"
AGENT_RUN_ROOT = ROOT / "workspace" / "runs" / "agent-runs"
DEFAULT_PROJECT_IDENTIFIER = "cento-agent-work"
DEFAULT_PROJECT_NAME = "Cento Agent Work"
RUNTIME_REGISTRY_PATH = ROOT / "data" / "agent-runtimes.json"
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
ACTIVE_RUN_STATUSES = {"planned", "launching", "running"}
ENDED_RUN_STATUSES = {"dry_run", "succeeded", "failed", "blocked", "stale", "exited_unknown"}
REMOTE_RECONCILE_TIMEOUT_SECONDS = int(os.environ.get("CENTO_RUN_REMOTE_RECONCILE_TIMEOUT", "8"))
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
BOOTSTRAP_CACHE: dict[str, Any] | None = None


class AgentWorkError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def json_from_mixed_stdout(value: str) -> dict[str, Any]:
    start = value.find("{")
    end = value.rfind("}")
    if start < 0 or end < start:
        return {}
    try:
        payload = json.loads(value[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def remote_run_status(record: dict[str, Any]) -> dict[str, Any]:
    node = str(record.get("node") or "")
    run_id = str(record.get("run_id") or "")
    if not node or not run_id or node == current_node():
        return {}
    if node != "linux":
        return {"remote_reconcile": "unsupported_node", "remote_node": node}
    command = (
        "cd /home/alice/projects/cento && "
        f"python3 scripts/agent_work.py run-status {shlex.quote(run_id)} --json --reconcile"
    )
    try:
        proc = subprocess.run(
            [cento_command(), "bridge", "to-linux", "--", command],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=REMOTE_RECONCILE_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"remote_reconcile": "unreachable", "remote_node": node, "remote_error": str(exc)}
    if proc.returncode != 0:
        return {
            "remote_reconcile": "failed",
            "remote_node": node,
            "remote_exit_code": proc.returncode,
            "remote_error": (proc.stderr or proc.stdout)[-1000:],
        }
    payload = json_from_mixed_stdout(proc.stdout)
    if not payload:
        return {"remote_reconcile": "invalid_json", "remote_node": node, "remote_error": proc.stdout[-1000:]}
    payload["remote_reconcile"] = "ok"
    payload["remote_node"] = node
    return payload


def remote_agent_run_records(*, active: bool = False) -> list[dict[str, Any]]:
    if current_node() == "linux":
        return []
    command_parts = ["python3", "scripts/agent_work.py", "runs", "--json"]
    if active:
        command_parts.append("--active")
    command = "cd /home/alice/projects/cento && " + shlex.join(command_parts)
    try:
        proc = subprocess.run(
            [cento_command(), "bridge", "to-linux", "--", command],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=REMOTE_RECONCILE_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if proc.returncode != 0:
        return []
    payload = json_from_mixed_stdout(proc.stdout)
    runs = payload.get("runs") if isinstance(payload, dict) else []
    if not isinstance(runs, list):
        return []
    records: list[dict[str, Any]] = []
    for item in runs:
        if isinstance(item, dict):
            record = dict(item)
            if str(record.get("node") or "").lower() == "linux":
                record["node"] = "linux"
            record["listed_from_remote_node"] = "linux"
            records.append(record)
    return records


def reconcile_agent_run(record: dict[str, Any], *, write: bool = False, remote: bool = True) -> dict[str, Any]:
    reconciled = dict(record)
    status = str(reconciled.get("status") or "unknown")
    pid_running = pid_alive(reconciled.get("pid")) or pid_alive(reconciled.get("child_pid"))
    tmux_running = tmux_session_alive(str(reconciled.get("tmux_session") or ""))
    reconciled["pid_alive"] = pid_running
    reconciled["tmux_alive"] = tmux_running
    if status in ACTIVE_RUN_STATUSES:
        if pid_running or tmux_running:
            reconciled["status"] = "running"
            reconciled["health"] = "running"
        elif remote and str(reconciled.get("node") or "") not in {"", current_node()}:
            remote_status = remote_run_status(reconciled)
            reconciled["remote_reconcile"] = remote_status.get("remote_reconcile", "")
            reconciled["remote_node"] = remote_status.get("remote_node", reconciled.get("node", ""))
            if remote_status.get("remote_reconcile") == "ok":
                reconciled["remote_status"] = remote_status.get("status", "")
                reconciled["remote_health"] = remote_status.get("health", "")
                reconciled["remote_pid"] = remote_status.get("pid") or remote_status.get("child_pid")
                reconciled["remote_tmux_alive"] = remote_status.get("tmux_alive")
                if str(remote_status.get("status") or "") in ACTIVE_RUN_STATUSES and (
                    remote_status.get("pid_alive") or remote_status.get("tmux_alive")
                ):
                    reconciled["status"] = "running"
                    reconciled["health"] = "remote_running"
                else:
                    reconciled["status"] = str(remote_status.get("status") or "stale")
                    reconciled["health"] = f"remote_{remote_status.get('health') or 'unknown'}"
                    if not reconciled.get("ended_at") and reconciled["status"] in ENDED_RUN_STATUSES:
                        reconciled["ended_at"] = now_iso()
            else:
                reconciled["status"] = "stale"
                reconciled["health"] = f"stale_remote_{remote_status.get('remote_reconcile') or 'unknown'}"
                if remote_status.get("remote_error"):
                    reconciled["remote_error"] = remote_status.get("remote_error")
                if not reconciled.get("ended_at"):
                    reconciled["ended_at"] = now_iso()
        else:
            reconciled["status"] = "stale"
            reconciled["health"] = "stale_no_process"
            if not reconciled.get("ended_at"):
                reconciled["ended_at"] = now_iso()
    elif status in {"succeeded", "dry_run"}:
        reconciled["health"] = "ok"
    elif status in {"failed", "blocked", "stale", "exited_unknown", "invalid"}:
        reconciled["health"] = reconciled.get("health") or status
    else:
        reconciled["health"] = "unknown"
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


def agent_run_records(*, include_untracked: bool = True, reconcile: bool = False, remote: bool = True) -> list[dict[str, Any]]:
    records = [reconcile_agent_run(record, write=reconcile, remote=remote) for record in load_agent_runs()]
    if include_untracked:
        records.extend(untracked_interactive_runs(records))
    if remote:
        by_id = {str(record.get("run_id") or ""): index for index, record in enumerate(records) if record.get("run_id")}
        for remote_record in remote_agent_run_records():
            run_id = str(remote_record.get("run_id") or "")
            if not run_id:
                continue
            if run_id in by_id:
                records[by_id[run_id]].update({"remote_listing": remote_record})
            else:
                by_id[run_id] = len(records)
                records.append(remote_record)
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


def docker_psql_args(sql: str) -> list[str]:
    return [
        "docker",
        "exec",
        "cento-redmine-postgres",
        "psql",
        "-U",
        "redmine",
        "-d",
        "redmine",
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
    transport = os.environ.get("CENTO_REDMINE_TRANSPORT", "auto").lower()
    base = docker_psql_args(sql)
    commands: list[list[str]] = []

    if transport in {"auto", "local"} and current_node() == "linux":
        commands.append(base)
        commands.append(["sg", "docker", "-c", shlex.join(base)])

    if transport in {"auto", "direct"} and current_node() != "linux":
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        known_hosts = STATE_DIR / "agent-work-known-hosts"
        host = os.environ.get("CENTO_REDMINE_SSH", "alice@alisapad.local")
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
        raise AgentWorkError(f"Unsupported CENTO_REDMINE_TRANSPORT={transport!r}")
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
        # Keep notes in Redmine with @cento agent-work update ISSUE_ID --status running --note "..."@.
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
) -> int:
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


def list_issues(include_closed: bool = False) -> list[dict[str, Any]]:
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
                coalesce((select cv.value from custom_values cv join custom_fields cf on cf.id = cv.custom_field_id where cv.customized_type = 'Issue' and cv.customized_id = i.id and cf.name = 'Cento Work Package' limit 1), '') as package
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


def show_issue(issue_id: int) -> dict[str, Any]:
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
    payload = ensure_bootstrap()
    print(json.dumps({"ok": True, **payload}, indent=2))
    return 0


def command_create(args: argparse.Namespace) -> int:
    issue_id = create_issue(args.title, args.description or "", args.node or "", args.agent or "", args.package or "default", role=args.role)
    issue = show_issue(issue_id)
    if args.json:
        print(json.dumps(issue, indent=2, default=str))
    else:
        print(f"created #{issue_id}: {issue['subject']}")
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
    result_label = result.upper()
    evidence_lines = "\n".join(f"* @{item}@" for item in evidence) if evidence else "* No evidence paths provided."
    body = note.strip() or "No validation note provided."
    return textwrap.dedent(
        f"""\
        h3. Validator {result_label}

        *Result:* {result_label}

        *Validation*
        {body}

        *Evidence*
        {evidence_lines}
        """
    )


def command_validate(args: argparse.Namespace) -> int:
    node = args.node or current_node()
    agent = args.agent or os.environ.get("USER") or "validator"
    enforce_validator_authorized(agent)
    result = args.result.lower()
    status = "review" if result == "pass" else "blocked"
    note = validation_note(result, args.note or "", args.evidence or [])
    report = json.dumps(
        {
            "result": result,
            "agent": agent,
            "node": node,
            "evidence": args.evidence or [],
            "updated_at": now_iso(),
        },
        sort_keys=True,
    )
    issue = update_issue(args.issue, status, note, node, agent, None, role="validator", validation_report=report)
    if args.json:
        print(json.dumps(issue, indent=2, default=str))
    else:
        print(f"validated #{issue['id']}: {result.upper()} -> {issue['status']}")
    return 0


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
        )
        command_dispatch(dispatch_args)
    return 0


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


def validation_report_markdown(issue_id: int, manifest_path: Path, result: str, checks: list[dict[str, Any]], evidence: list[str]) -> str:
    lines = [
        f"# Validation Report For #{issue_id}",
        "",
        f"Generated: {now_iso()}",
        f"Manifest: `{display_path(manifest_path)}`",
        f"Result: **{result.upper()}**",
        "",
        "## Checks",
        "",
    ]
    for item in checks:
        status = "PASS" if item.get("ok") else "FAIL"
        lines.append(f"- **{status}** `{item.get('type')}` {item.get('name')}: {item.get('message')}")
    lines.extend(["", "## Evidence", ""])
    if evidence:
        lines.extend(f"- `{item}`" for item in evidence)
    else:
        lines.append("- No evidence paths produced.")
    return "\n".join(lines) + "\n"


def command_validate_run(args: argparse.Namespace) -> int:
    issue = show_issue(args.issue)
    node = args.node or current_node()
    agent = args.agent or os.environ.get("USER") or "validator"
    manifest_path = resolve_root_path(args.manifest or f"workspace/runs/agent-work/{args.issue}/validation.json")
    manifest = load_validation_manifest(manifest_path)
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
    result = "pass" if all(item.get("ok") for item in results) else "fail"
    report_path = resolve_root_path(str(format_manifest_value(manifest.get("report") or str(manifest_path.parent / "validation-report.md"), context)))
    report_json_path = report_path.with_suffix(".json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_evidence = [display_path(report_path), display_path(report_json_path)]
    all_evidence = evidence + [item for item in report_evidence if item not in evidence]
    payload = {
        "issue": args.issue,
        "subject": issue.get("subject"),
        "result": result,
        "agent": agent,
        "node": node,
        "manifest": display_path(manifest_path),
        "evidence": all_evidence,
        "checks": results,
        "updated_at": now_iso(),
    }
    report_path.write_text(validation_report_markdown(args.issue, manifest_path, result, results, all_evidence), encoding="utf-8")
    report_json_path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    note = args.note or f"validate-run {result.upper()} using {display_path(manifest_path)}"
    if not args.no_update:
        status = "review" if result == "pass" else "blocked"
        update_issue(
            args.issue,
            status,
            validation_note(result, note, all_evidence),
            node,
            agent,
            None,
            role="validator",
            validation_report=json.dumps(payload, sort_keys=True, default=str),
        )
    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(f"validate-run #{args.issue}: {result.upper()} report={display_path(report_path)}")
        for item in results:
            status = "PASS" if item.get("ok") else "FAIL"
            print(f"{status} {item.get('name')}: {item.get('message')}")
    return 0 if result == "pass" else 1


def agent_prompt(issue: dict[str, Any], role: str = "builder") -> str:
    role = normalize_role(role)
    if role == "validator":
        role_protocol = textwrap.dedent(
            f"""\
            Protocol:
            1. Start by running: cento agent-work claim {issue['id']} --node "$(uname -s)" --agent "$USER" --role validator
            2. Do not implement product code unless the issue explicitly asks for validator tooling.
            3. If a validation manifest exists, run: cento agent-work validate-run {issue['id']} --manifest PATH
            4. Otherwise run the stated checks, inspect screenshots or rendered output, and verify evidence paths exist.
            5. Pass with: cento agent-work validate {issue['id']} --result pass --evidence PATH --note "..."
            6. Fail or block with: cento agent-work validate {issue['id']} --result fail --evidence PATH --note "..."

            Only a Validator pass moves the issue to Review.
            """
        )
    else:
        role_protocol = textwrap.dedent(
            f"""\
            Protocol:
            1. Start by running: cento agent-work claim {issue['id']} --node "$(uname -s)" --agent "$USER" --role builder
            2. If that route is not registered on this node, use: python3 scripts/agent_work.py claim {issue['id']} --node "$(uname -s)" --agent "$USER" --role builder
            3. Do the smallest coherent implementation for this issue only.
            4. Keep Redmine updated with: cento agent-work update {issue['id']} --status running --role builder --note "..."
            5. When implementation is ready, create the handoff with: cento agent-work handoff {issue['id']} --summary "..." --changed-file PATH --command "..." --evidence PATH
            6. If blocked, use: cento agent-work update {issue['id']} --status blocked --role builder --note "blocked because ..."

            Builders do not move issues to Review. Review is reserved for Validator pass.
            """
        )
    return textwrap.dedent(
        f"""\
        You are a Cento {role} agent working a tracked Redmine issue.

        Issue: #{issue['id']} {issue['subject']}
        Project: {issue['project']}
        Status: {issue['status']}
        Node: {issue.get('node') or 'unassigned'}
        Agent: {issue.get('agent') or 'unassigned'}
        Role: {role}
        Package: {issue.get('package') or 'default'}

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
    records = agent_run_records(include_untracked=not args.no_untracked, reconcile=args.reconcile, remote=not args.no_remote_reconcile)
    if args.issue is not None:
        records = [item for item in records if item.get("issue_id") == args.issue]
    if args.active:
        active_statuses = ACTIVE_RUN_STATUSES | {"untracked_interactive", "stale"}
        records = [item for item in records if str(item.get("status") or "") in active_statuses]
    if args.json:
        print(json.dumps({"runs": records, "count": len(records), "updated_at": now_iso()}, indent=2, default=str))
    else:
        print_agent_run_table(records)
    return 0


def command_run_status(args: argparse.Namespace) -> int:
    record = load_agent_run(args.run_id)
    record = reconcile_agent_run(record, write=args.reconcile, remote=not args.no_remote_reconcile)
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
          else
            "${{agent_work_cmd[@]}}" update {issue['id']} --status validating --role builder --note {shlex.quote(f"Builder session {session} finished with {runtime_id}; ready for validator; log: {log_path}")} || true
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


def dispatch_pool_candidates(args: argparse.Namespace) -> list[dict[str, Any]]:
    wanted_status = str(args.status or "queued").lower()
    items = list_issues(include_closed=False)
    candidates: list[dict[str, Any]] = []
    for issue in items:
        if str(issue.get("status") or "").lower() != wanted_status:
            continue
        node = str(issue.get("node") or "")
        if not args.node and node and node not in {"linux", "macos"}:
            continue
        if not args.include_epics and str(issue.get("tracker") or "") != "Agent Task":
            continue
        if args.package and str(issue.get("package") or "") != args.package:
            continue
        if args.node and str(issue.get("node") or "") != args.node:
            continue
        if args.role and str(issue.get("role") or "") != args.role:
            continue
        candidates.append(issue)
    candidates.sort(key=lambda item: int(item["id"]))
    return candidates[: max(int(args.limit or 1), 0)]


def dispatch_pool_plan(args: argparse.Namespace) -> list[dict[str, Any]]:
    runtime = args.runtime or "codex"
    model = args.model or "gpt-5.3-codex-spark"
    role_override = args.role or ""
    planned = []
    for issue in dispatch_pool_candidates(args):
        node = args.node or str(issue.get("node") or "linux")
        role = role_override or str(issue.get("role") or "builder") or "builder"
        agent = args.agent or str(issue.get("agent") or "spark-worker")
        command = [
            "cento",
            "agent-work",
            "dispatch",
            str(issue["id"]),
            "--node",
            node,
            "--agent",
            agent,
            "--role",
            role,
            "--runtime",
            runtime,
            "--model",
            model,
        ]
        planned.append(
            {
                "issue": issue["id"],
                "title": issue["subject"],
                "status": issue["status"],
                "package": issue.get("package") or "",
                "node": node,
                "agent": agent,
                "role": role,
                "runtime": runtime,
                "model": model,
                "command": shlex.join(command),
            }
        )
    return planned


def command_dispatch_pool(args: argparse.Namespace) -> int:
    plan = dispatch_pool_plan(args)
    payload = {
        "execute": bool(args.execute),
        "count": len(plan),
        "limit": int(args.limit or 1),
        "status": args.status,
        "package": args.package,
        "node": args.node,
        "role": args.role,
        "runtime": args.runtime or "codex",
        "model": args.model or "gpt-5.3-codex-spark",
        "planned": plan,
    }
    if args.json and not args.execute:
        print(json.dumps(payload, indent=2, default=str))
        return 0
    if not plan:
        if args.json:
            print(json.dumps(payload, indent=2, default=str))
        else:
            print("No dispatch-pool candidates.")
        return 0
    if not args.execute:
        print(f"dispatch-pool plan: {len(plan)} candidate(s). Re-run with --execute to start agents.")
        for item in plan:
            print(f"- #{item['issue']} {item['runtime']} {item['model']} on {item['node']}: {item['command']}")
        return 0

    results = []
    for item in plan:
        dispatch_args = argparse.Namespace(
            issue=int(item["issue"]),
            node=item["node"],
            agent=item["agent"],
            role=item["role"],
            runtime=item["runtime"],
            model=item["model"],
            dry_run=False,
        )
        rc = command_dispatch(dispatch_args)
        results.append({"issue": item["issue"], "returncode": rc})
        if rc != 0 and not args.keep_going:
            break
    if args.json:
        payload["results"] = results
        print(json.dumps(payload, indent=2, default=str))
    return 0 if all(item["returncode"] == 0 for item in results) else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Redmine-backed Cento agent work.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("bootstrap", help="Create the Redmine project, statuses, tracker, and fields.")
    p.set_defaults(func=command_bootstrap)

    p = sub.add_parser("create", help="Create one agent task.")
    p.add_argument("--title", required=True)
    p.add_argument("--description", default="")
    p.add_argument("--node", default="")
    p.add_argument("--agent", default="")
    p.add_argument("--role", choices=ROLE_CHOICES, default="builder")
    p.add_argument("--package", default="default")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=command_create)

    p = sub.add_parser("split", help="Create an agent work package and task issues.")
    p.add_argument("--title", required=True)
    p.add_argument("--goal", default="")
    p.add_argument("--task", action="append", required=True)
    p.add_argument("--node", default="")
    p.add_argument("--nodes", default="")
    p.add_argument("--agent", default="")
    p.add_argument("--role", choices=ROLE_CHOICES, default="builder")
    p.add_argument("--package", default="")
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
        "validate-run",
        help="Run validation.json checks and record Validator result.",
        description="Run validation.json checks and record Validator result.",
    )
    p.add_argument("issue", type=int)
    p.add_argument("--manifest", default="")
    p.add_argument("--note", default="")
    p.add_argument("--node", default="")
    p.add_argument("--agent", default="")
    p.add_argument("--no-update", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=command_validate_run)

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
    p.add_argument("--no-remote-reconcile", action="store_true", help="Do not query remote nodes for remote run status.")
    p.add_argument("--reconcile", action="store_true", help="Update stale ledger records based on ps/tmux state.")
    p.set_defaults(func=command_runs)

    p = sub.add_parser("run-status", help="Show one agent run ledger entry.")
    p.add_argument("run_id")
    p.add_argument("--reconcile", action="store_true")
    p.add_argument("--no-remote-reconcile", action="store_true", help="Do not query remote nodes for remote run status.")
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
    p.set_defaults(func=command_dispatch)

    p = sub.add_parser("dispatch-pool", help="Plan or execute cheap Spark/Codex dispatches for queued work.")
    p.add_argument("--limit", type=int, default=2)
    p.add_argument("--status", choices=sorted(STATUS_MAP), default="queued")
    p.add_argument("--package", default="")
    p.add_argument("--node", default="")
    p.add_argument("--agent", default="")
    p.add_argument("--role", choices=ROLE_CHOICES, default="")
    p.add_argument("--runtime", default="codex")
    p.add_argument("--model", default="gpt-5.3-codex-spark")
    p.add_argument("--include-epics", action="store_true", help="Include non-Agent Task issues such as epics.")
    p.add_argument("--execute", action="store_true", help="Actually dispatch planned issues. Default is plan-only.")
    p.add_argument("--keep-going", action="store_true", help="Continue dispatching after one issue fails.")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=command_dispatch_pool)

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
