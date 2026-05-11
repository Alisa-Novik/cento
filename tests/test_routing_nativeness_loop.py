#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import walk_autopilot as walk  # noqa: E402
import story_manifest  # noqa: E402


def sample_raw_counts(*, cron_installed: bool = False) -> dict:
    return {
        "schema_version": "cento.routing_nativeness.raw_counts.v1",
        "collected_at": "2026-05-05T00:00:00Z",
        "privacy": {"mode": "counts-only", "raw_prompt_or_log_excerpts": False},
        "git": {"dirty_count": 0, "status_counts": {}},
        "cron": {"installed": cron_installed},
        "tools": {
            "tool_count": 52,
            "walk_autopilot_registered": True,
            "walk_autopilot_command_count": 4,
            "walk_autopilot_routing_command_count": 0,
        },
        "cli_docs": {"human_routing_doc_exists": False},
        "walk_autopilot": {"run_id": "walk-autopilot-1", "metrics_records": 1},
        "self_improve": {
            "status": "unknown",
            "validation_status": "unknown",
            "promotion_recommendation": "unknown",
        },
        "agent_work": {"count": 8, "stale_count": 1, "failed_count": 2, "demo_test_run_count": 3},
        "codex_observability": {"row_count": 100, "error_count": 79},
        "skill_usage": {"terms": walk.SKILL_TERMS, "total_counts": {"cento-native": 4}},
        "cento_native_skill_drift": {"drift_count": 1},
    }


def test_routing_cron_install_status_and_uninstall(tmp_path: Path) -> None:
    crontab = tmp_path / "crontab.txt"
    crontab.write_text("# existing\n* * * * * echo keep\n", encoding="utf-8")

    install_args = argparse.Namespace(every_hours=4, crontab_file=str(crontab), dry_run=False, json=True)
    assert walk.command_routing_install_cron(install_args) == 0
    text = crontab.read_text(encoding="utf-8")
    assert walk.ROUTING_CRON_BEGIN in text
    assert "0 */4 * * *" in text
    assert "echo keep" in text
    assert walk.routing_cron_status(str(crontab))["installed"] is True

    uninstall_args = argparse.Namespace(crontab_file=str(crontab), dry_run=False, json=True)
    assert walk.command_routing_uninstall_cron(uninstall_args) == 0
    text = crontab.read_text(encoding="utf-8")
    assert walk.ROUTING_CRON_BEGIN not in text
    assert "echo keep" in text


def test_decision_rules_emit_expected_actions() -> None:
    decision = walk.decide_routing_changes(sample_raw_counts(), dirty_before=2, dirty_after=2)
    action_ids = {item["id"] for item in decision["actions"]}

    assert decision["authority"] == "report_then_task"
    assert decision["cron_may_implement"] is False
    assert decision["agent_work_allowed"] is True
    assert "install_routing_cron" in action_ids
    assert "repair_self_improve_before_heavy_cron" in action_ids
    assert "sync_cento_native_skill" in action_ids
    assert "agent_work_hygiene_cleanup" in action_ids
    assert "codex_error_observability" in action_ids


def test_dirty_count_change_blocks_agent_work() -> None:
    decision = walk.decide_routing_changes(sample_raw_counts(cron_installed=True), dirty_before=1, dirty_after=2)

    assert decision["agent_work_allowed"] is False
    assert any(item["id"] == "dirty_worktree_changed_during_loop" for item in decision["actions"])


def test_skill_usage_counts_do_not_persist_raw_lines(tmp_path: Path) -> None:
    source = tmp_path / "history.jsonl"
    source.write_text(
        '{"message":"use cento-native but do not store this prompt"}\n'
        '{"message":"ui-verify-and-report ui-verify-and-report"}\n',
        encoding="utf-8",
    )

    payload = walk.count_skill_mentions_in_file(source, ["cento-native", "ui-verify-and-report"])
    encoded = json.dumps(payload)

    assert payload["counts"]["cento-native"] == 1
    assert payload["counts"]["ui-verify-and-report"] == 2
    assert "do not store this prompt" not in encoded
    assert "message" not in encoded


def test_agent_run_aggregation_is_counts_only() -> None:
    payload = {
        "runs": [
            {"status": "stale", "health": "stale_no_process", "role": "builder", "runtime": "codex", "issue_subject": "Secret demo task"},
            {"status": "running", "health": "running", "role": "validator", "runtime": "claude-code", "issue_subject": "Private live task"},
        ]
    }
    summary = walk.aggregate_agent_runs(payload, {"exit_code": 0})
    encoded = json.dumps(summary)

    assert summary["count"] == 2
    assert summary["stale_count"] == 1
    assert summary["demo_test_run_count"] == 1
    assert "Secret demo task" not in encoded
    assert "Private live task" not in encoded


def test_routing_run_writes_artifacts_without_agent_work(monkeypatch, tmp_path: Path, capsys) -> None:
    routing_root = tmp_path / "routing-native"
    monkeypatch.setattr(walk, "ROUTING_RUN_ROOT", routing_root)
    monkeypatch.setattr(walk, "ROUTING_LATEST_DIR", routing_root / "latest")
    monkeypatch.setattr(walk, "count_dirty_files", lambda: 0)
    monkeypatch.setattr(walk, "collect_routing_raw_counts", lambda _crontab_file="": sample_raw_counts(cron_installed=True))

    args = argparse.Namespace(run_id="routing-native-test", crontab_file="", no_agent_work=True, json=True)
    assert walk.command_routing_run(args) == 0
    output = json.loads(capsys.readouterr().out)
    run_dir = routing_root / "routing-native-test"

    assert output["status"] == "completed"
    assert (run_dir / "raw_counts.json").exists()
    assert (run_dir / "decision.json").exists()
    assert (run_dir / "decision_report.md").exists()
    assert (run_dir / "agent-work-story.json").exists()
    assert (routing_root / "latest" / "decision_report.md").exists()
    request = json.loads((run_dir / "agent_work_request.json").read_text(encoding="utf-8"))
    assert request["status"] == "skipped_no_agent_work"


def test_routing_agent_story_manifest_is_valid(tmp_path: Path) -> None:
    decision = walk.decide_routing_changes(sample_raw_counts(cron_installed=True), dirty_before=0, dirty_after=0)
    payload = walk.routing_story_payload(decision, tmp_path / "routing-native-test")

    assert story_manifest.validate_manifest(payload, check_links=False) == []
