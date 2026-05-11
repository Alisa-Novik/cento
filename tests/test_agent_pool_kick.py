#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import agent_pool_kick as pool


def test_manifest_repair_writes_canonical_small_task_story(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(pool, "ROOT", tmp_path)
    issue = {
        "id": 42,
        "subject": "docs heartbeat evidence cleanup",
        "description": "Tighten the evidence note and keep validation deterministic.",
        "status": "Queued",
        "role": "builder",
        "package": "agent-ops",
    }

    repairs = pool.repair_missing_manifests([issue], apply=True, limit=3)

    story_path = tmp_path / "workspace" / "runs" / "agent-work" / "42" / "story.json"
    validation_path = tmp_path / "workspace" / "runs" / "agent-work" / "42" / "validation.json"
    story = json.loads(story_path.read_text(encoding="utf-8"))
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    route = pool.planned_validation_route(issue)

    assert repairs == [
            {
                "issue": 42,
                "lane": "small",
                "subject": "docs heartbeat evidence cleanup",
                "story_manifest": "workspace/runs/agent-work/42/story.json",
                "validation_manifest": "workspace/runs/agent-work/42/validation.json",
                "story_missing": True,
                "validation_missing": True,
                "applied": True,
                "forced": False,
            }
        ]
    assert story["issue"]["id"] == 42
    assert story["validation"]["mode"] == "no-model"
    assert validation["coverage"]["automation_coverage_percent"] == 100.0
    assert route["mode"] == "no-model"
    assert route["validation_manifest"] == "workspace/runs/agent-work/42/validation.json"


def test_manifest_repair_dry_run_does_not_write(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(pool, "ROOT", tmp_path)
    issue = {"id": 43, "subject": "template pool fix", "status": "Queued", "role": "builder"}

    repairs = pool.repair_missing_manifests([issue], apply=False, limit=1)

    assert repairs[0]["applied"] is False
    assert not (tmp_path / "workspace" / "runs" / "agent-work" / "43" / "story.json").exists()


def test_manifest_repair_handles_builder_and_coordinator_lanes(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(pool, "ROOT", tmp_path)
    issues = [
        {"id": 44, "subject": "Route prompt through hard proreq", "status": "Queued", "role": "builder"},
        {"id": 45, "subject": "Coordinate app section tasks", "status": "Queued", "role": "coordinator"},
    ]

    repairs = pool.repair_missing_manifests(issues, apply=True, limit=5, lanes=("builder", "coordinator"))

    assert [item["lane"] for item in repairs] == ["builder", "coordinator"]
    builder_story = json.loads((tmp_path / "workspace" / "runs" / "agent-work" / "44" / "story.json").read_text(encoding="utf-8"))
    coordinator_story = json.loads((tmp_path / "workspace" / "runs" / "agent-work" / "45" / "story.json").read_text(encoding="utf-8"))
    assert builder_story["lane"]["role"] == "builder"
    assert coordinator_story["lane"]["role"] == "coordinator"
    assert builder_story["validation"]["no_model_eligible"] is True


def test_manifest_repair_validator_uses_model_route(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(pool, "ROOT", tmp_path)
    issue = {"id": 46, "subject": "Validate dashboard evidence", "status": "Queued", "role": "validator"}

    repairs = pool.repair_missing_manifests([issue], apply=True, limit=5, lanes=("validator",))
    story = json.loads((tmp_path / "workspace" / "runs" / "agent-work" / "46" / "story.json").read_text(encoding="utf-8"))
    route = pool.planned_validation_route(issue)

    assert repairs[0]["lane"] == "validator"
    assert story["lane"]["role"] == "validator"
    assert story["validation"]["mode"] == "cheap-model"
    assert story["validation"]["no_model_eligible"] is False
    assert route["mode"] == "cheap-model"


def test_manifest_repair_can_force_recently_blocked_issue(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(pool, "ROOT", tmp_path)
    issue = {"id": 47, "subject": "Route prompt through hard proreq", "status": "Blocked", "role": "builder"}

    repairs = pool.repair_missing_manifests([issue], apply=False, limit=5, lanes=("builder",), issue_ids={47})

    assert repairs[0]["issue"] == 47
    assert repairs[0]["lane"] == "builder"
    assert repairs[0]["forced"] is True


def test_runtime_override_can_force_claude_code_model() -> None:
    runtime = pool.dispatch_runtime(None, "claude-code")

    assert runtime == "claude-code"
    assert pool.dispatch_model(runtime, None) == pool.DEFAULT_CLAUDE_MODEL
    assert pool.dispatch_model(runtime, "claude-test-model") == "claude-test-model"
