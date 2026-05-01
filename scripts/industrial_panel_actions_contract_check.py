#!/usr/bin/env python3
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent
REPO_DIR = ROOT_DIR.parent
EVIDENCE_DIR = REPO_DIR / "workspace" / "runs" / "agent-work" / "46" / "current-state"
SCRIPT_DIR = str(ROOT_DIR)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_panel(*, action_fixture: Path | None = None, cluster_fixture: Path | None = None):
    env_map = {
        "CENTO_INDUSTRIAL_ACTIONS_FIXTURE": str(action_fixture) if action_fixture else "",
        "CENTO_INDUSTRIAL_CLUSTER_FIXTURE": str(cluster_fixture) if cluster_fixture else "",
    }
    for key, value in env_map.items():
        if value:
            os.environ[key] = value
        else:
            os.environ.pop(key, None)
    import industrial_panel

    return importlib.reload(industrial_panel)


def assert_registry_shape(actions: list[dict[str, Any]]) -> None:
    required = {
        "key",
        "id",
        "label",
        "description",
        "allowlist",
        "command",
        "dry_run_command",
        "target_node",
        "availability_check",
        "expected_output_signal",
    }
    for action in actions:
        missing = sorted(required.difference(action))
        assert_true(not missing, f"action missing fields: {missing}")
        assert_true(bool(action.get("label")), f"action label missing: {action}")
        assert_true(bool(action.get("description")), f"action description missing: {action}")
        assert_true(bool(action.get("allowlist")), f"action allowlist missing: {action}")
        assert_true(bool(action.get("command")), f"action command missing: {action}")
        assert_true(bool(action.get("dry_run_command")), f"action dry-run missing: {action}")
        assert_true(bool(action.get("target_node")), f"action target node missing: {action}")
        assert_true(bool(action.get("availability_check")), f"action availability check missing: {action}")
        assert_true(bool(action.get("expected_output_signal")), f"action expected signal missing: {action}")


def row_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("id") or ""): row for row in rows}


def write_snapshot(name: str, content: str) -> Path:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    path = EVIDENCE_DIR / name
    path.write_text(content, encoding="utf-8")
    return path


def assert_row_status(rows: list[dict[str, Any]], action_id: str, expected_available: bool) -> None:
    row = row_map(rows).get(action_id)
    assert_true(row is not None, f"missing registry row for {action_id}")
    assert_true(bool(row.get("available")) is expected_available, f"unexpected availability for {action_id}: {row}")


def assert_dry_run_signals(panel: Any, actions: list[dict[str, Any]]) -> None:
    for action in actions:
        output_lines = panel.run_action(action, dry_run=True)
        output_text = "\n".join(output_lines)
        expected = str(action.get("expected_output_signal") or "")
        assert_true(expected in output_text, f"dry-run missing expected signal {expected!r}: {output_lines}")


def assert_fixture_statuses(panel: Any, fixture_name: str, expected: list[str]) -> None:
    actions = panel.load_quick_actions()
    statuses = [panel.execute_action(action)["status"] for action in actions]
    assert_true(statuses == expected, f"{fixture_name} statuses mismatch: {statuses}")


def reset_action_state(panel: Any) -> None:
    with panel.ACTIONS_STATE_LOCK:
        panel.ACTIONS_STATE["selected"] = 0
        panel.ACTIONS_STATE["running"] = None
        panel.ACTIONS_STATE["message"] = "ready"
        panel.ACTIONS_STATE["output"] = ["j/k or arrows move", "1-5 select", "enter runs selected action", "d dry-runs selected action", "q quits panel"]
        panel.ACTIONS_STATE["last_key"] = ""
        panel.ACTIONS_STATE["results"] = {}


def render_actions_snapshot(panel: Any, name: str) -> Path:
    output = panel.strip_ansi(panel.render_frame("actions"))
    return write_snapshot(name, output)


def main() -> int:
    fixture_root = ROOT_DIR / "fixtures" / "industrial_panel"

    live_panel = load_panel()
    live_actions = live_panel.load_quick_actions()
    assert_true(len(live_actions) >= 5, f"expected at least 5 actions, got {len(live_actions)}")
    assert_registry_shape(live_actions)

    live_payload, live_error = live_panel.action_cluster_payload()
    assert_true(live_error is None, f"live cluster payload error: {live_error}")
    live_health = live_payload.get("health") or {}
    live_nodes = live_health.get("nodes") or []
    assert_true(str(live_health.get("overall") or "") == "degraded", f"live cluster should be degraded: {live_health}")
    assert_true(any(str(node.get("id") or "") == "iphone" and str(node.get("state") or "") == "offline" for node in live_nodes), f"live cluster should include offline iphone: {live_health}")

    live_rows = live_panel.build_action_rows(live_payload, live_error)
    assert_row_status(live_rows, "cluster_status", True)
    assert_row_status(live_rows, "cluster_nodes", True)
    assert_row_status(live_rows, "cluster_heal", True)
    assert_row_status(live_rows, "iphone_heartbeat", True)
    assert_row_status(live_rows, "preset_session", True)
    assert_true(all(str(row.get("availability_reason") or "") == "ready" for row in live_rows), f"live actions should be ready: {live_rows}")
    assert_dry_run_signals(live_panel, live_actions)

    live_actions_plain = live_panel.strip_ansi(live_panel.render_frame("actions"))
    assert_true("IDLE Cluster status" in live_actions_plain, "actions panel should show idle result before any run")
    assert_true("No action has run yet." in live_actions_plain, "actions panel should explain the idle result state")

    validation_panel = load_panel(
        action_fixture=fixture_root / "validation_actions.json",
        cluster_fixture=fixture_root / "cluster-empty.json",
    )
    validation_actions = validation_panel.load_quick_actions()
    assert_true([action["id"] for action in validation_actions] == ["selected_ok", "selected_fail", "selected_blocked"], f"unexpected validation action ids: {validation_actions}")
    validation_rows = validation_panel.build_action_rows(*validation_panel.action_cluster_payload())
    assert_row_status(validation_rows, "selected_ok", True)
    assert_row_status(validation_rows, "selected_fail", True)
    assert_row_status(validation_rows, "selected_blocked", False)
    blocked_row = row_map(validation_rows)["selected_blocked"]
    assert_true("unsafe shell wrapper blocked" in str(blocked_row.get("availability_reason") or ""), f"unsafe command should be blocked: {blocked_row}")

    dry_run_output = validation_panel.run_action(validation_actions[0], dry_run=True)
    assert_true(dry_run_output[0].startswith("SUCCEEDED:"), f"dry-run should succeed: {dry_run_output}")
    assert_true("selected dry-run ok" in "\n".join(dry_run_output), f"dry-run output missing signal: {dry_run_output}")

    reset_action_state(validation_panel)
    with validation_panel.ACTIONS_STATE_LOCK:
        validation_panel.ACTIONS_STATE["selected"] = 0
    selected_snapshot = render_actions_snapshot(validation_panel, "actions-selected.txt")

    reset_action_state(validation_panel)
    with validation_panel.ACTIONS_STATE_LOCK:
        validation_panel.ACTIONS_STATE["selected"] = 0
        validation_panel.ACTIONS_STATE["running"] = "selected_ok"
        validation_panel.ACTIONS_STATE["message"] = "running: Selected ok"
        validation_panel.ACTIONS_STATE["output"] = ["running ..."]
    running_snapshot = render_actions_snapshot(validation_panel, "actions-running.txt")

    reset_action_state(validation_panel)
    succeeded_result = validation_panel.execute_action(validation_actions[0])
    with validation_panel.ACTIONS_STATE_LOCK:
        validation_panel.ACTIONS_STATE["selected"] = 0
        validation_panel.ACTIONS_STATE["results"] = {"selected_ok": succeeded_result}
        validation_panel.ACTIONS_STATE["message"] = f"{succeeded_result['status']} ({succeeded_result['label']})"
        validation_panel.ACTIONS_STATE["output"] = list(succeeded_result.get("output") or [])
    succeeded_snapshot = render_actions_snapshot(validation_panel, "actions-succeeded.txt")

    reset_action_state(validation_panel)
    failed_result = validation_panel.execute_action(validation_actions[1])
    with validation_panel.ACTIONS_STATE_LOCK:
        validation_panel.ACTIONS_STATE["selected"] = 1
        validation_panel.ACTIONS_STATE["results"] = {"selected_fail": failed_result}
        validation_panel.ACTIONS_STATE["message"] = f"{failed_result['status']} ({failed_result['label']})"
        validation_panel.ACTIONS_STATE["output"] = list(failed_result.get("output") or [])
    failed_snapshot = render_actions_snapshot(validation_panel, "actions-failed.txt")

    reset_action_state(validation_panel)
    with validation_panel.ACTIONS_STATE_LOCK:
        validation_panel.ACTIONS_STATE["selected"] = 2
    blocked_snapshot = render_actions_snapshot(validation_panel, "actions-blocked.txt")

    dry_run_snapshot = write_snapshot("actions-dry-run.txt", "\n".join(dry_run_output) + "\n")

    degraded_panel = load_panel(cluster_fixture=fixture_root / "cluster-degraded.json")
    degraded_rows = degraded_panel.build_action_rows(*degraded_panel.action_cluster_payload())
    assert_row_status(degraded_rows, "cluster_status", True)
    assert_row_status(degraded_rows, "cluster_nodes", True)
    assert_row_status(degraded_rows, "cluster_heal", True)
    assert_row_status(degraded_rows, "iphone_heartbeat", True)
    assert_row_status(degraded_rows, "preset_session", True)

    empty_panel = load_panel(cluster_fixture=fixture_root / "cluster-empty.json")
    empty_rows = empty_panel.build_action_rows(*empty_panel.action_cluster_payload())
    assert_row_status(empty_rows, "cluster_status", True)
    assert_row_status(empty_rows, "cluster_nodes", False)
    assert_row_status(empty_rows, "cluster_heal", False)
    assert_row_status(empty_rows, "iphone_heartbeat", False)
    assert_row_status(empty_rows, "preset_session", True)

    empty_actions_panel = load_panel(action_fixture=fixture_root / "empty_actions.json")
    assert_true(empty_actions_panel.load_quick_actions() == [], "empty actions fixture should render no actions")

    assert_fixture_statuses(load_panel(action_fixture=fixture_root / "unavailable_action.json"), "unavailable_action", ["blocked"])
    assert_fixture_statuses(load_panel(action_fixture=fixture_root / "empty_action.json"), "empty_action", ["empty"])
    assert_fixture_statuses(load_panel(action_fixture=fixture_root / "degraded_action.json"), "degraded_action", ["failed"])

    validation_report = write_snapshot(
        "validation-report.md",
        "\n".join(
            [
                "# Industrial Actions Validation",
                "",
                "Commands:",
                "- `python3 scripts/industrial_panel_actions_contract_check.py`",
                "- `python3 scripts/industrial_panel.py actions --once --plain`",
                "- `./scripts/industrial_panel_e2e.sh`",
                "",
                "Evidence:",
                f"- `{selected_snapshot.relative_to(REPO_DIR)}`",
                f"- `{running_snapshot.relative_to(REPO_DIR)}`",
                f"- `{succeeded_snapshot.relative_to(REPO_DIR)}`",
                f"- `{failed_snapshot.relative_to(REPO_DIR)}`",
                f"- `{blocked_snapshot.relative_to(REPO_DIR)}`",
                f"- `{dry_run_snapshot.relative_to(REPO_DIR)}`",
            ]
        )
        + "\n",
    )

    print(f"snapshot: {selected_snapshot.relative_to(REPO_DIR)}")
    print(f"snapshot: {running_snapshot.relative_to(REPO_DIR)}")
    print(f"snapshot: {succeeded_snapshot.relative_to(REPO_DIR)}")
    print(f"snapshot: {failed_snapshot.relative_to(REPO_DIR)}")
    print(f"snapshot: {blocked_snapshot.relative_to(REPO_DIR)}")
    print(f"snapshot: {dry_run_snapshot.relative_to(REPO_DIR)}")
    print(f"report: {validation_report.relative_to(REPO_DIR)}")

    print("industrial actions contract check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
