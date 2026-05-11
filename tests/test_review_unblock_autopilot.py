#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import story_manifest  # noqa: E402
import walk_autopilot as walk  # noqa: E402


def issue(issue_id: int, status: str, *, package: str = "pkg", role: str = "builder", test_artifact: bool = False) -> dict:
    return {
        "id": issue_id,
        "subject": f"Issue {issue_id}",
        "status": status,
        "package": package,
        "role": role,
        "node": "linux",
        "agent": "alice",
        "is_closed": status.lower() in {"done", "closed"},
        "test_artifact": test_artifact,
    }


def write_canonical_manifests(root: Path, issue_id: int) -> None:
    run_dir = root / "workspace" / "runs" / "agent-work" / str(issue_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "story.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "issue": {"id": issue_id, "title": f"Issue {issue_id}", "package": "pkg"},
                "lane": {"owner": "alice", "node": "linux", "agent": "alice", "role": "builder"},
                "paths": {"run_dir": f"workspace/runs/agent-work/{issue_id}"},
                "scope": {"goal": "Validate issue.", "acceptance": ["Validation is recorded."]},
                "expected_outputs": [
                    {
                        "path": f"workspace/runs/agent-work/{issue_id}/worker-handoff.md",
                        "description": "Worker handoff.",
                        "owner": "builder",
                        "required": True,
                    }
                ],
                "validation": {
                    "manifest": f"workspace/runs/agent-work/{issue_id}/validation.json",
                    "mode": "no-model",
                    "no_model_eligible": True,
                    "risk": "medium",
                    "escalation_triggers": ["missing_manifest", "failed_deterministic_command", "ambiguity"],
                    "commands": ["python3 -m json.tool workspace/runs/agent-work/{issue}/story.json"],
                },
                "deliverables": {
                    "manifest": f"workspace/runs/agent-work/{issue_id}/deliverables.json",
                    "hub": f"workspace/runs/agent-work/{issue_id}/start-here.html",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "validation.json").write_text('{"checks":[],"coverage":{"automation_coverage_percent":100}}\n', encoding="utf-8")


def sample_snapshot() -> dict:
    return {
        "recovery": {
            "review": {"packages_ready": [{"package": "pkg", "count": 1, "issue_ids": [10]}]},
            "blocked_requeue": [{"id": 20, "package": "pkg", "role": "validator", "reason": "old dispatch can be requeued"}],
            "follow_up_candidates": [
                {
                    "source_issue_id": 60,
                    "package": "pkg",
                    "reason": "internal-artifact-gap",
                    "title": "Repair blocked issue 60",
                    "description": "Create a narrow follow-up.",
                }
            ],
            "runs": {
                "stale_items": [
                    {"run_id": "issue-30-stale", "issue_id": 30, "role": "validator", "status": "stale"},
                    {"run_id": "issue-21-stale", "issue_id": 21, "role": "builder", "status": "stale"},
                ]
            },
        },
        "issues": {
            "issues": [
                issue(10, "Review"),
                issue(11, "Validating"),
                issue(20, "Blocked", role="validator"),
                issue(21, "Blocked"),
                issue(30, "Done"),
                issue(40, "Blocked", test_artifact=True),
                issue(50, "Validating"),
            ]
        },
        "runs": {"runs": []},
        "commands": {
            "recovery_plan": {"exit_code": 0, "json_ok": True},
            "agent_work_list": {"exit_code": 0, "json_ok": True},
            "agent_work_runs": {"exit_code": 0, "json_ok": True},
        },
    }


def test_review_unblock_decision_emits_expected_actions(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(walk, "ROOT", tmp_path)
    write_canonical_manifests(tmp_path, 11)

    decision = walk.decide_review_unblock(sample_snapshot(), mode="aggressive", dirty_before=7, dirty_after=7)
    types = [item["type"] for item in decision["actions"]]

    assert decision["apply_allowed"] is True
    assert "close_done" in types
    assert "validate_local" in types
    assert "requeue_stale_dispatch" in types
    assert "repair_task" in types
    assert "close_demo_test" in types
    assert "archive_stale_historical" in types
    assert "operator_needed" in types
    assert all(item["apply"] for item in decision["actions"] if item["type"] in walk.REVIEW_UNBLOCK_MUTATING_TYPES)


def test_report_mode_never_applies_mutating_actions(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(walk, "ROOT", tmp_path)
    write_canonical_manifests(tmp_path, 11)

    decision = walk.decide_review_unblock(sample_snapshot(), mode="report", dirty_before=0, dirty_after=0)

    assert decision["apply_allowed"] is False
    assert not any(item["apply"] for item in decision["actions"])


def test_dirty_count_change_blocks_mutations(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(walk, "ROOT", tmp_path)
    write_canonical_manifests(tmp_path, 11)

    decision = walk.decide_review_unblock(sample_snapshot(), mode="aggressive", dirty_before=1, dirty_after=2)

    assert decision["apply_allowed"] is False
    assert not any(item["apply"] for item in decision["actions"])
    assert any(item["type"] == "operator_needed" and "dirty" in item["reason"].lower() for item in decision["actions"])


def test_review_close_cap_is_issue_count_based() -> None:
    snapshot = {"recovery": {"review": {"packages_ready": [{"package": "big", "count": 25, "issue_ids": list(range(25))}]}}, "issues": {"issues": []}, "runs": {"runs": []}, "commands": {}}

    decision = walk.decide_review_unblock(snapshot, mode="aggressive", dirty_before=0, dirty_after=0)
    types = [item["type"] for item in decision["actions"]]

    assert "close_done" not in types
    assert any(item["type"] == "operator_needed" and "close cap" in item["reason"] for item in decision["actions"])


def test_repair_story_payload_is_valid(tmp_path: Path) -> None:
    payload = walk.repair_story_payload(
        {
            "source_issue_id": 60,
            "package": "pkg",
            "title": "Repair blocked issue 60",
            "reason": "internal-artifact-gap",
            "description": "Repair the missing validation evidence.",
        },
        tmp_path,
    )

    assert story_manifest.validate_manifest(payload, check_links=False) == []


def test_apply_review_unblock_actions_materializes_transcripts(monkeypatch, tmp_path: Path) -> None:
    captured: list[list[str]] = []

    def fake_run_command(command: list[str], *, timeout: int, env: dict | None = None) -> dict:
        captured.append(command)
        return {
            "command": command,
            "command_text": " ".join(command),
            "exit_code": 0,
            "stdout_tail": "{}",
            "stderr_tail": "",
            "duration_seconds": 0,
            "timed_out": False,
        }

    monkeypatch.setattr(walk, "run_command", fake_run_command)
    actions = [
        {
            "id": "repair",
            "type": "repair_task",
            "issue_id": 60,
            "package": "pkg",
            "reason": "internal-artifact-gap",
            "apply": True,
            "command": ["./scripts/cento.sh", "agent-work", "create", "--manifest", "__STAGE_DRAFT_DIR__/repair-60.story.json"],
            "source_candidate": {"source_issue_id": 60, "package": "pkg", "title": "Repair blocked issue 60"},
        },
        {
            "id": "report",
            "type": "operator_needed",
            "issue_id": 70,
            "package": "pkg",
            "reason": "ambiguous",
            "apply": False,
            "command": ["echo", "skip"],
        },
    ]

    results = walk.apply_review_unblock_actions(actions, tmp_path)

    assert results[0]["status"] == "applied"
    assert results[1]["status"] == "skipped_report"
    assert captured and "repair-60.story.json" in " ".join(captured[0])
    assert (tmp_path / "actions" / "001-repair_task" / "drafts" / "repair-60.story.json").exists()
    assert (tmp_path / "actions.jsonl").read_text(encoding="utf-8").count("\n") == 2


def test_review_unblock_run_writes_latest_artifacts(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(walk, "REVIEW_UNBLOCK_RUN_ROOT", tmp_path / "review-unblock")
    monkeypatch.setattr(walk, "REVIEW_UNBLOCK_LATEST_DIR", tmp_path / "review-unblock" / "latest")
    monkeypatch.setattr(walk, "count_dirty_files", lambda: 0)
    monkeypatch.setattr(walk, "collect_review_unblock_snapshot", lambda _stage_dir: {"recovery": {}, "issues": {"issues": []}, "runs": {"runs": []}, "commands": {}})

    args = argparse.Namespace(run_id="review-unblock-test", mode="report", json=True)
    assert walk.command_review_unblock_run(args) == 0
    output = json.loads(capsys.readouterr().out)
    run_dir = tmp_path / "review-unblock" / "review-unblock-test"

    assert output["status"] == "completed"
    assert (run_dir / "decision.json").exists()
    assert (run_dir / "decision_report.md").exists()
    assert (tmp_path / "review-unblock" / "latest" / "decision_report.md").exists()
