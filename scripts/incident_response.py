#!/usr/bin/env python3

from __future__ import annotations

import argparse
import fcntl
import json
import os
import plistlib
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "cento"
STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "cento"
REQUEST_DIR = STATE_DIR / "cluster-requests"
STATE_FILE = STATE_DIR / "incidents.json"
LOCK_FILE = STATE_DIR / "incident-response.lock"
INCIDENT_KEY = "iphone-ce-ingress"
INCIDENT_TITLE = "[SEV2][iphone-ce-ingress] iPhone ce inbound command path not working"
INCIDENT_PACKAGE = "incident-response"
DEFAULT_HEARTBEAT_TTL_SECONDS = 15 * 60
DEFAULT_STUCK_AFTER_SECONDS = 10 * 60
DEFAULT_LOOKBACK_SECONDS = 24 * 60 * 60
DEFAULT_STORM_WINDOW_SECONDS = 15 * 60
DEFAULT_STORM_THRESHOLD = 5
DEFAULT_COOLDOWN_SECONDS = 6 * 60 * 60
DEFAULT_DAILY_LIMIT = 1


class IncidentError(RuntimeError):
    pass


@dataclass
class RequestRecord:
    request_id: str
    path: Path
    created_at: datetime
    request: str
    complete: bool
    exit_code: str
    hash_key: str

    @property
    def age_seconds(self) -> int:
        return max(0, int((now() - self.created_at).total_seconds()))


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None = None) -> str:
    return (dt or now()).isoformat()


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def read_text(path: Path, default: str = "") -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return default


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_request_time(request_id: str, path: Path) -> datetime:
    prefix = "-".join(request_id.split("-")[:2])
    try:
        local_dt = datetime.strptime(prefix, "%Y%m%d-%H%M%S").astimezone()
        return local_dt.astimezone(timezone.utc)
    except ValueError:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def heartbeat_state(ttl_seconds: int) -> dict[str, Any]:
    path = CONFIG_DIR / "heartbeats" / "iphone.json"
    data = read_json(path, {})
    last_seen = data.get("last_seen")
    if not last_seen:
        return {
            "ok": False,
            "reason": "missing heartbeat file or last_seen",
            "path": str(path),
            "age_seconds": None,
        }
    age = max(0, int(time.time() - int(last_seen)))
    return {
        "ok": age <= ttl_seconds,
        "reason": "ok" if age <= ttl_seconds else f"stale heartbeat age={age}s ttl={ttl_seconds}s",
        "path": str(path),
        "age_seconds": age,
        "last_seen": int(last_seen),
        "via": data.get("via", ""),
        "host": data.get("host", ""),
    }


def load_requests(lookback_seconds: int, limit: int = 600) -> list[RequestRecord]:
    if not REQUEST_DIR.exists():
        return []
    records: list[RequestRecord] = []
    cutoff = now() - timedelta(seconds=lookback_seconds)
    dirs = [path for path in REQUEST_DIR.iterdir() if path.is_dir()]
    dirs.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    for path in dirs[:limit]:
        request_id = path.name
        created_at = parse_request_time(request_id, path)
        if created_at < cutoff:
            continue
        request = read_text(path / "request.txt")
        exit_code = read_text(path / "exit_code")
        complete = bool(exit_code or (path / "final.txt").exists())
        hash_key = request_id.split("-")[-1] if "-" in request_id else request_id
        records.append(RequestRecord(request_id, path, created_at, request, complete, exit_code, hash_key))
    return records


def request_state(records: list[RequestRecord], stuck_after_seconds: int, storm_window_seconds: int, storm_threshold: int) -> dict[str, Any]:
    stuck = [record for record in records if not record.complete and record.age_seconds >= stuck_after_seconds]
    recent_cutoff = now() - timedelta(seconds=storm_window_seconds)
    recent_incomplete = [record for record in records if not record.complete and record.created_at >= recent_cutoff]
    storm_counts = Counter(record.hash_key for record in recent_incomplete)
    storms = [
        {"hash": hash_key, "count": count}
        for hash_key, count in sorted(storm_counts.items(), key=lambda item: item[1], reverse=True)
        if count >= storm_threshold
    ]
    successful = [record for record in records if record.complete and (record.exit_code == "0" or not record.exit_code)]
    latest = max(records, key=lambda record: record.created_at, default=None)
    latest_success = max(successful, key=lambda record: record.created_at, default=None)
    return {
        "ok": not stuck and not storms,
        "stuck_count": len(stuck),
        "stuck_requests": [record.request_id for record in stuck[:10]],
        "storm_count": len(storms),
        "storms": storms[:5],
        "recent_incomplete_count": len(recent_incomplete),
        "latest_request": latest.request_id if latest else "",
        "latest_request_age_seconds": latest.age_seconds if latest else None,
        "latest_success": latest_success.request_id if latest_success else "",
        "latest_success_age_seconds": latest_success.age_seconds if latest_success else None,
        "total_recent_requests": len(records),
    }


def evaluate_iphone_ce(args: argparse.Namespace) -> dict[str, Any]:
    heartbeat = heartbeat_state(args.heartbeat_ttl)
    records = load_requests(args.lookback)
    requests = request_state(records, args.stuck_after, args.storm_window, args.storm_threshold)
    reasons: list[str] = []
    if not heartbeat["ok"]:
        reasons.append(f"iphone heartbeat unhealthy: {heartbeat['reason']}")
    if requests["stuck_count"]:
        reasons.append(f"{requests['stuck_count']} cluster request(s) stuck beyond {args.stuck_after}s")
    if requests["storm_count"]:
        reasons.append(f"{requests['storm_count']} repeated request storm(s) detected")
    status = "unhealthy" if reasons else "healthy"
    return {
        "key": INCIDENT_KEY,
        "severity": "SEV2",
        "status": status,
        "reasons": reasons,
        "heartbeat": heartbeat,
        "requests": requests,
        "checked_at": iso(),
    }


def run_agent_work(argv: list[str], timeout: int = 25) -> dict[str, Any]:
    cmd = [sys.executable, str(ROOT / "scripts" / "agent_work.py"), *argv]
    proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "cmd": cmd,
    }


def active_incident_issue() -> dict[str, Any] | None:
    result = run_agent_work(["list", "--json"], timeout=25)
    if result["returncode"] != 0:
        raise IncidentError((result["stderr"] or result["stdout"] or "agent-work list failed").strip())
    payload = json.loads(result["stdout"])
    for issue in payload.get("issues", []):
        subject = issue.get("subject", "")
        package = issue.get("package", "")
        if INCIDENT_TITLE in subject or (INCIDENT_KEY in subject and package == INCIDENT_PACKAGE):
            return issue
    return None


def incident_description(evaluation: dict[str, Any], guardrail: dict[str, Any]) -> str:
    heartbeat = evaluation["heartbeat"]
    requests = evaluation["requests"]
    reasons = "\n".join(f"- {reason}" for reason in evaluation["reasons"]) or "- No unhealthy signal."
    stuck = ", ".join(requests.get("stuck_requests") or []) or "none"
    storms = ", ".join(f"{item['hash']} x{item['count']}" for item in requests.get("storms") or []) or "none"
    return f"""SEV2 incident created by `cento incident check iphone-ce`.

Impact:
- iPhone `ce "send me ..."` command submission may hang, fail silently, or not reach the Mac control plane.
- User-visible symptom: commands from iPhone do not produce an iPhone notification or tracked cluster request completion.

Evidence:
{reasons}

Signals:
- heartbeat_ok: {heartbeat.get("ok")}
- heartbeat_age_seconds: {heartbeat.get("age_seconds")}
- latest_request: {requests.get("latest_request") or "none"}
- latest_success: {requests.get("latest_success") or "none"}
- stuck_requests: {stuck}
- request_storms: {storms}

Guardrails:
- incident_key: {INCIDENT_KEY}
- cooldown_seconds: {guardrail["cooldown_seconds"]}
- max_creates_per_day: {guardrail["max_creates_per_day"]}
- existing active issue is reused instead of creating a duplicate
- state_file: {STATE_FILE}

Initial triage:
1. On iPhone/iSH, run: `$HOME/bin/cento-remote cluster status`.
2. Run: `ce 'send me iphone inbound test'`.
3. If direct remote works but `ce` does not, reinstall the companion helper:
   `$HOME/bin/cento-remote cluster companion-setup iphone > /tmp/cento-setup.sh && sh /tmp/cento-setup.sh && . ~/.profile`.
4. On Mac, inspect: `cento incident check iphone-ce --json --no-create`.
5. Check the Mac request spool: `{REQUEST_DIR}`.
6. Check companion setup: `{CONFIG_DIR / "companions" / "iphone-ish-setup.sh"}`.
"""


def load_state() -> dict[str, Any]:
    return read_json(STATE_FILE, {"incidents": {}})


def save_state(state: dict[str, Any]) -> None:
    write_json(STATE_FILE, state)


def recent_create_count(entry: dict[str, Any], window_seconds: int = 24 * 60 * 60) -> int:
    cutoff = now() - timedelta(seconds=window_seconds)
    events = [parse_iso(item) for item in entry.get("create_events", [])]
    return sum(1 for event in events if event and event >= cutoff)


def can_create(entry: dict[str, Any], args: argparse.Namespace) -> tuple[bool, str]:
    if args.force:
        return True, "force bypassed cooldown and daily limit"
    last_created = parse_iso(entry.get("last_created_at"))
    if last_created and (now() - last_created).total_seconds() < args.cooldown:
        return False, f"cooldown active until {(last_created + timedelta(seconds=args.cooldown)).isoformat()}"
    if recent_create_count(entry) >= args.max_creates_per_day:
        return False, f"daily create limit reached ({args.max_creates_per_day}/24h)"
    return True, "allowed"


def record_noisy_suppression(entry: dict[str, Any], reason: str) -> None:
    entry["last_suppressed_at"] = iso()
    entry["last_suppressed_reason"] = reason
    entry["suppressed_count"] = int(entry.get("suppressed_count", 0)) + 1


def create_incident(evaluation: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with LOCK_FILE.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = load_state()
        incidents = state.setdefault("incidents", {})
        entry = incidents.setdefault(INCIDENT_KEY, {})
        entry["last_checked_at"] = evaluation["checked_at"]
        entry["last_status"] = evaluation["status"]
        entry["last_reasons"] = evaluation["reasons"]
        guardrail = {
            "cooldown_seconds": args.cooldown,
            "max_creates_per_day": args.max_creates_per_day,
        }
        if evaluation["status"] == "healthy":
            entry["last_healthy_at"] = evaluation["checked_at"]
            save_state(state)
            return {"action": "none", "reason": "healthy"}
        if args.no_create:
            entry["last_unhealthy_at"] = evaluation["checked_at"]
            save_state(state)
            return {"action": "no_create", "reason": "creation disabled"}
        try:
            existing = active_incident_issue()
        except Exception as exc:
            entry["last_create_error_at"] = iso()
            entry["last_create_error"] = str(exc)
            save_state(state)
            return {"action": "error", "reason": str(exc)}
        if existing:
            entry["open_issue_id"] = existing.get("id")
            entry["last_unhealthy_at"] = evaluation["checked_at"]
            save_state(state)
            return {"action": "existing", "issue_id": existing.get("id"), "reason": "active incident already exists"}
        allowed, reason = can_create(entry, args)
        if not allowed:
            record_noisy_suppression(entry, reason)
            save_state(state)
            return {"action": "suppressed", "reason": reason}
        description = incident_description(evaluation, guardrail)
        result = run_agent_work(
            [
                "create",
                "--title",
                INCIDENT_TITLE,
                "--description",
                description,
                "--node",
                "macos",
                "--agent",
                "incident-response",
                "--package",
                INCIDENT_PACKAGE,
                "--json",
            ],
            timeout=35,
        )
        if result["returncode"] != 0:
            error = (result["stderr"] or result["stdout"] or "agent-work create failed").strip()
            entry["last_create_error_at"] = iso()
            entry["last_create_error"] = error
            save_state(state)
            return {"action": "error", "reason": error}
        issue = json.loads(result["stdout"])
        issue_id = issue.get("id")
        entry["open_issue_id"] = issue_id
        entry["last_created_at"] = iso()
        entry.setdefault("create_events", []).append(entry["last_created_at"])
        entry["last_unhealthy_at"] = evaluation["checked_at"]
        save_state(state)
        return {"action": "created", "issue_id": issue_id, "reason": reason}


def command_check(args: argparse.Namespace) -> int:
    if args.target != "iphone-ce":
        raise IncidentError("Only target supported in this MVP: iphone-ce")
    evaluation = evaluate_iphone_ce(args)
    incident = create_incident(evaluation, args)
    payload = {"evaluation": evaluation, "incident": incident}
    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(f"iphone-ce {evaluation['status']}: {incident['action']}")
        for reason in evaluation["reasons"]:
            print(f"- {reason}")
        if incident.get("issue_id"):
            print(f"issue #{incident['issue_id']}")
        elif incident.get("reason"):
            print(incident["reason"])
    return 2 if args.strict and evaluation["status"] == "unhealthy" else 0


def command_status(args: argparse.Namespace) -> int:
    state = load_state()
    if args.json:
        print(json.dumps(state, indent=2, default=str))
    else:
        entry = state.get("incidents", {}).get(INCIDENT_KEY, {})
        if not entry:
            print("No incident-response state recorded.")
        else:
            print(f"{INCIDENT_KEY}: {entry.get('last_status', 'unknown')}")
            if entry.get("open_issue_id"):
                print(f"open_issue_id={entry['open_issue_id']}")
            if entry.get("last_created_at"):
                print(f"last_created_at={entry['last_created_at']}")
            if entry.get("last_suppressed_reason"):
                print(f"last_suppressed_reason={entry['last_suppressed_reason']}")
    return 0


def launch_agent_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / "com.cento.incident.iphone-ce.plist"


def launch_agent_payload(interval: int) -> dict[str, Any]:
    log_path = STATE_DIR / "incident-response.log"
    command = f'cd {ROOT} && /usr/bin/python3 scripts/incident_response.py check iphone-ce --json >> {log_path} 2>&1'
    return {
        "Label": "com.cento.incident.iphone-ce",
        "ProgramArguments": ["/bin/zsh", "-lc", command],
        "RunAtLoad": True,
        "StartInterval": interval,
        "StandardOutPath": str(log_path),
        "StandardErrorPath": str(STATE_DIR / "incident-response.err"),
    }


def command_install(args: argparse.Namespace) -> int:
    if args.target != "iphone-ce":
        raise IncidentError("Only target supported in this MVP: iphone-ce")
    if sys.platform != "darwin":
        raise IncidentError("launchd install is only supported on macOS")
    plist = launch_agent_path()
    payload = launch_agent_payload(args.interval)
    if args.dry_run:
        print(plist)
        print(plistlib.dumps(payload).decode("utf-8"))
        return 0
    plist.parent.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    plist.write_bytes(plistlib.dumps(payload))
    if not args.no_start:
        subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}", str(plist)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        subprocess.run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(plist)], check=False)
        subprocess.run(["launchctl", "kickstart", "-k", f"gui/{os.getuid()}/com.cento.incident.iphone-ce"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    print(f"installed {plist}")
    return 0


def command_uninstall(args: argparse.Namespace) -> int:
    if args.target != "iphone-ce":
        raise IncidentError("Only target supported in this MVP: iphone-ce")
    plist = launch_agent_path()
    subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}", str(plist)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    if plist.exists():
        plist.unlink()
    print(f"uninstalled {plist}")
    return 0


def command_docs(_args: argparse.Namespace) -> int:
    print((ROOT / "docs" / "incident-response.md").read_text(encoding="utf-8"))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Cento incident response checks and guarded agent-work escalation.")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="Run a bounded incident check.")
    check.add_argument("target", choices=["iphone-ce"])
    check.add_argument("--json", action="store_true")
    check.add_argument("--no-create", action="store_true", help="Do not create an agent-work issue.")
    check.add_argument("--force", action="store_true", help="Bypass cooldown and daily creation limit.")
    check.add_argument("--strict", action="store_true", help="Exit 2 when unhealthy.")
    check.add_argument("--heartbeat-ttl", type=int, default=DEFAULT_HEARTBEAT_TTL_SECONDS)
    check.add_argument("--stuck-after", type=int, default=DEFAULT_STUCK_AFTER_SECONDS)
    check.add_argument("--lookback", type=int, default=DEFAULT_LOOKBACK_SECONDS)
    check.add_argument("--storm-window", type=int, default=DEFAULT_STORM_WINDOW_SECONDS)
    check.add_argument("--storm-threshold", type=int, default=DEFAULT_STORM_THRESHOLD)
    check.add_argument("--cooldown", type=int, default=DEFAULT_COOLDOWN_SECONDS)
    check.add_argument("--max-creates-per-day", type=int, default=DEFAULT_DAILY_LIMIT)
    check.set_defaults(func=command_check)

    status = sub.add_parser("status", help="Show local incident guardrail state.")
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=command_status)

    install = sub.add_parser("install", help="Install a macOS launchd watcher.")
    install.add_argument("target", choices=["iphone-ce"])
    install.add_argument("--interval", type=int, default=300)
    install.add_argument("--dry-run", action="store_true")
    install.add_argument("--no-start", action="store_true")
    install.set_defaults(func=command_install)

    uninstall = sub.add_parser("uninstall", help="Remove the macOS launchd watcher.")
    uninstall.add_argument("target", choices=["iphone-ce"])
    uninstall.set_defaults(func=command_uninstall)

    docs = sub.add_parser("docs", help="Print incident response documentation.")
    docs.set_defaults(func=command_docs)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except subprocess.TimeoutExpired as exc:
        print(f"[ERROR] command timed out: {exc}", file=sys.stderr)
        return 1
    except (IncidentError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
