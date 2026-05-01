#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import tempfile
from pathlib import Path

import agent_manager


def iso_minutes_ago(minutes: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


def assert_has(item: dict, label: str) -> None:
    labels = item.get("labels") or []
    if label not in labels:
        raise AssertionError(f"expected label {label!r}, got {labels!r}")


def stuck_validator_fixture() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        log_path = Path(tmp) / "claude-code.log"
        log_path.write_text("")
        run = {
            "run_id": "issue-81-fixture",
            "issue_id": 81,
            "status": "running",
            "health": "running",
            "role": "validator",
            "runtime": "claude-code",
            "pid": 1000,
            "pid_alive": True,
            "tmux_alive": True,
            "tmux_session": "cento-agent-81-fixture",
            "started_at": iso_minutes_ago(45),
            "log_path": str(log_path),
        }
        issues = {81: {"id": 81, "status": "Running", "subject": "fixture"}}
        processes = {
            1000: {"pid": 1000, "ppid": 1, "pcpu": 0.0, "pmem": 0.1, "elapsed_seconds": 2700, "args": "claude --print"},
            1001: {"pid": 1001, "ppid": 1000, "pcpu": 0.0, "pmem": 0.1, "elapsed_seconds": 2600, "args": "zsh -c python3 - <<EOF"},
            1002: {"pid": 1002, "ppid": 1001, "pcpu": 0.0, "pmem": 0.0, "elapsed_seconds": 2600, "args": "cat"},
        }
        item = agent_manager.classify_run(run, issues, processes, {81: 1})
        assert item["severity"] == "critical"
        assert_has(item, "stuck")
        assert_has(item, "long_running_validator")
        assert_has(item, "blocked_child_command")


def stale_done_fixture() -> None:
    run = {
        "run_id": "issue-65-fixture",
        "issue_id": 65,
        "status": "stale",
        "health": "stale_no_process",
        "role": "validator",
        "runtime": "claude-code",
        "pid_alive": False,
        "tmux_alive": False,
        "started_at": iso_minutes_ago(120),
        "ended_at": iso_minutes_ago(90),
    }
    issues = {65: {"id": 65, "status": "Done", "subject": "fixture"}}
    item = agent_manager.classify_run(run, issues, {}, {})
    assert item["severity"] == "warning"
    assert_has(item, "stale")
    assert_has(item, "issue_done_mismatch")
    assert_has(item, "historical_done_stale")
    actions = item.get("actions") or []
    if not any(action.get("id") == "archive_historical_stale" for action in actions):
        raise AssertionError(f"expected archive action, got {actions!r}")


def stale_open_fixture() -> None:
    run = {
        "run_id": "issue-57-fixture",
        "issue_id": 57,
        "status": "stale",
        "health": "stale_no_process",
        "role": "validator",
        "runtime": "codex",
        "pid_alive": False,
        "tmux_alive": False,
        "started_at": iso_minutes_ago(120),
        "ended_at": iso_minutes_ago(90),
    }
    issues = {57: {"id": 57, "status": "Review", "subject": "fixture"}}
    item = agent_manager.classify_run(run, issues, {}, {})
    assert item["severity"] == "warning"
    assert_has(item, "stale")
    if "historical_done_stale" in (item.get("labels") or []):
        raise AssertionError(f"open issue should not be historical stale: {item!r}")
    actions = item.get("actions") or []
    if not any(action.get("id") == "reconcile_ledger" for action in actions):
        raise AssertionError(f"expected reconcile action, got {actions!r}")


def archived_fixture() -> None:
    run = {
        "run_id": "issue-65-archived-fixture",
        "issue_id": 65,
        "status": "archived",
        "health": "historical_done_stale",
        "role": "validator",
        "runtime": "claude-code",
        "pid_alive": False,
        "tmux_alive": False,
        "started_at": iso_minutes_ago(120),
        "ended_at": iso_minutes_ago(90),
    }
    issues = {65: {"id": 65, "status": "Done", "subject": "fixture"}}
    item = agent_manager.classify_run(run, issues, {}, {})
    assert item["severity"] == "ok"
    assert_has(item, "archived")


def duplicate_fixture() -> None:
    run = {
        "run_id": "issue-42-fixture",
        "issue_id": 42,
        "status": "running",
        "health": "running",
        "role": "builder",
        "runtime": "codex",
        "pid_alive": True,
        "tmux_alive": False,
        "started_at": iso_minutes_ago(5),
    }
    issues = {42: {"id": 42, "status": "Running", "subject": "fixture"}}
    item = agent_manager.classify_run(run, issues, {}, {42: 2})
    assert item["severity"] == "critical"
    assert_has(item, "duplicate")


def main() -> int:
    stuck_validator_fixture()
    stale_done_fixture()
    stale_open_fixture()
    archived_fixture()
    duplicate_fixture()
    print("agent-manager-contract-ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
