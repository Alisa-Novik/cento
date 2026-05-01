#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from industrial_activity import build_activity_events


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "scripts" / "fixtures" / "industrial_panel" / "activity"
CURRENT_STATE_ROOT = ROOT / "workspace" / "runs" / "agent-work" / "industrial-panels-v1" / "current-state"
NOW = 1_777_500_000.0


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_fixture(name: str) -> tuple[Path, dict[str, object]]:
    path = FIXTURE_ROOT / name
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert_true(isinstance(payload, dict), f"fixture root must be an object: {path}")
    return path, payload


def render_panel(fixture: Path | None = None, extra_args: list[str] | None = None) -> str:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "scripts")
    env["COLUMNS"] = "120"
    if fixture is not None:
        env["CENTO_INDUSTRIAL_ACTIVITY_FIXTURE"] = str(fixture)
    args = [sys.executable, "scripts/industrial_panel.py", "activity", "--once", "--plain"]
    if extra_args:
        args.extend(extra_args)
    result = subprocess.run(
        args,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert_true(result.returncode == 0, result.stderr or result.stdout)
    return result.stdout


def write_snapshot(name: str, output: str) -> Path:
    CURRENT_STATE_ROOT.mkdir(parents=True, exist_ok=True)
    path = CURRENT_STATE_ROOT / name
    path.write_text(output, encoding="utf-8")
    return path


def check_feed_fixture() -> Path:
    fixture_path, payload = load_fixture("feed.json")
    log_root = FIXTURE_ROOT / str(payload.get("log_root") or "feed/logs")
    rows = build_activity_events(
        log_root=log_root,
        cluster_payload=payload.get("cluster_payload") if isinstance(payload.get("cluster_payload"), dict) else None,
        jobs_payload=payload.get("jobs_payload") if isinstance(payload.get("jobs_payload"), dict) else None,
        agent_payload=payload.get("agent_payload") if isinstance(payload.get("agent_payload"), dict) else None,
        limit=20,
        now=NOW,
        include_placeholders=bool(payload.get("include_placeholders", True)),
    )
    by_source = [row["source"] for row in rows]
    messages = [row["message"] for row in rows]
    assert_true(messages.count("Industrial workspace 1 composed") == 1, f"duplicate suppression failed: {messages}")
    merged_sources = [row.get("sources") for row in rows if row["message"] == "Industrial workspace 1 composed"]
    assert_true(merged_sources == [["industrial-os", "industrial-workspace"]], f"duplicate source labels not merged: {merged_sources}")
    assert_true(("dashboard" in by_source), f"raw HTTP log missing: {rows}")
    assert_true(("redmine" in by_source), f"JSONL redmine log missing: {rows}")
    assert_true(any(row["source"] == "jobs" and row["severity"] == "critical" for row in rows), f"job event missing: {rows}")
    assert_true(any(row["source"] == "agent-work" and row["metadata"].get("issue_id") == 42 for row in rows), f"Redmine issue event missing: {rows}")
    assert_true(any(row["source"] == "cluster" and row["severity"] == "critical" for row in rows), f"cluster severity missing: {rows}")
    assert_true(any(row["severity"] == "warning" for row in rows), f"warning severity missing: {rows}")
    output = render_panel(fixture_path)
    assert_true("FILTERS" in output, f"activity filter summary missing: {output}")
    assert_true("SEV" in output and "SOURCE" in output, f"activity panel header missing: {output}")
    assert_true("industrial-os + industrial-workspace" in output, f"duplicate source label missing from panel output: {output}")
    assert_true("Redmine issue 42" in output or "redmine" in output.lower(), f"redmine log row missing: {output}")
    assert_true("#42 Validating: Industrial OS Activity Feed Panel" in output, f"Redmine issue panel row missing: {output}")
    cluster_only = render_panel(fixture_path, ["--source", "cluster"])
    assert_true("FILTERS source=cluster" in cluster_only, f"source filter summary missing: {cluster_only}")
    assert_true("dashboard" not in cluster_only.lower(), f"source filter leaked dashboard rows: {cluster_only}")
    assert_true("jobs" not in cluster_only.lower(), f"source filter leaked jobs rows: {cluster_only}")
    assert_true("cluster degraded" in cluster_only, f"source filter dropped cluster rows: {cluster_only}")
    return write_snapshot("activity-feed.txt", output)


def check_empty_fixture() -> Path:
    fixture_path, payload = load_fixture("empty.json")
    log_root = FIXTURE_ROOT / str(payload.get("log_root") or "empty/logs")
    rows = build_activity_events(
        log_root=log_root,
        cluster_payload=payload.get("cluster_payload") if isinstance(payload.get("cluster_payload"), dict) else None,
        jobs_payload=payload.get("jobs_payload") if isinstance(payload.get("jobs_payload"), dict) else None,
        agent_payload=payload.get("agent_payload") if isinstance(payload.get("agent_payload"), dict) else None,
        limit=20,
        now=NOW,
        include_placeholders=bool(payload.get("include_placeholders", False)),
    )
    assert_true(rows == [], f"empty fixture should render no events: {rows}")
    output = render_panel(fixture_path)
    assert_true("No activity events found." in output, f"empty panel state missing: {output}")
    return write_snapshot("activity-empty.txt", output)


def check_unavailable_fixture() -> Path:
    fixture_path, payload = load_fixture("unavailable.json")
    log_root = FIXTURE_ROOT / str(payload.get("log_root") or "unavailable/logs")
    rows = build_activity_events(
        log_root=log_root,
        cluster_payload=payload.get("cluster_payload") if isinstance(payload.get("cluster_payload"), dict) else None,
        jobs_payload=payload.get("jobs_payload") if isinstance(payload.get("jobs_payload"), dict) else None,
        agent_payload=payload.get("agent_payload") if isinstance(payload.get("agent_payload"), dict) else None,
        limit=8,
        now=NOW,
        include_placeholders=bool(payload.get("include_placeholders", True)),
    )
    assert_true(len(rows) == 1, f"unavailable fixture should render one placeholder row: {rows}")
    assert_true(rows[0]["message"] == "cluster snapshot unavailable", f"unavailable fixture row mismatch: {rows}")
    output = render_panel(fixture_path, ["--severity", "warning"])
    assert_true("FILTERS severity=warning" in output, f"severity filter summary missing: {output}")
    assert_true("cluster snapshot unavailable" in output, f"unavailable panel state missing: {output}")
    return write_snapshot("activity-unavailable.txt", output)


def check_live_snapshot() -> Path:
    output = render_panel(None)
    assert_true("ACTIVITY FEED" in output, f"live panel header missing: {output}")
    assert_true("cluster" in output.lower(), f"live cluster row missing: {output}")
    return write_snapshot("activity-live.txt", output)


def main() -> int:
    feed_snapshot = check_feed_fixture()
    empty_snapshot = check_empty_fixture()
    unavailable_snapshot = check_unavailable_fixture()
    live_snapshot = check_live_snapshot()
    print(f"feed snapshot: {feed_snapshot}")
    print(f"empty snapshot: {empty_snapshot}")
    print(f"unavailable snapshot: {unavailable_snapshot}")
    print(f"live snapshot: {live_snapshot}")
    print("industrial activity contract check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
