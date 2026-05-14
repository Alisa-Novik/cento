#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import parallel_delivery_taskstream as taskstream  # noqa: E402


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_split_plan_loads_successfully(tmp_path: Path) -> None:
    split_plan = taskstream.build_fixture_split_plan(tmp_path, base_commit="abc123")
    plan = taskstream.load_split_plan(split_plan)

    assert plan.run_id == "taskstream-fixture"
    assert len(plan.tasks) == 3
    assert plan.tasks[0].task_id == "task-src-helper"
    assert plan.tasks[2].route == "manifest-only"


def test_dry_run_emits_work_packages_and_report(tmp_path: Path) -> None:
    split_plan = taskstream.build_fixture_split_plan(tmp_path / "fixture", base_commit="abc123")
    report = taskstream.emit_taskstream_manifests(
        split_plan_path=split_plan,
        out_dir=tmp_path / "fixture",
        transport="manifest-only",
        run_preflight=True,
        timestamp=taskstream.DEFAULT_TIMESTAMP,
    )

    assert report.mode == "dry-run"
    assert report.live_creation_attempted is False
    assert report.task_count == 3
    assert report.agent_work_routed_count == 2
    assert report.manifest_only_count == 1
    assert report.preflight["status"] == "passed"

    for task_id in ["task-src-helper", "task-tests", "task-evidence-only"]:
        package = tmp_path / "fixture" / "work-packages" / task_id
        assert (package / "story.json").exists()
        assert (package / "validation.json").exists()
        assert (package / "handoff.md").exists()
        assert (package / "agent-work-command.txt").exists()

    payload = read_json(tmp_path / "fixture" / "taskstream-handoff-report.json")
    assert payload["schema"] == "cento.parallel_delivery.taskstream_handoff_report.v1"
    assert payload["story_manifest_count"] == 3
    assert payload["validation_manifest_count"] == 3
    assert (tmp_path / "fixture" / "taskstream-handoff-report.md").exists()
    assert (tmp_path / "fixture" / "validation-summary.txt").exists()


def test_preflight_command_validates_generated_work_packages(tmp_path: Path) -> None:
    split_plan = taskstream.build_fixture_split_plan(tmp_path / "fixture", base_commit="abc123")
    taskstream.emit_taskstream_manifests(split_plan_path=split_plan, out_dir=tmp_path / "fixture", run_preflight=False)

    payload = taskstream.run_preflight_command(tmp_path / "fixture" / "work-packages", tmp_path / "preflight")

    assert payload["status"] == "passed"
    assert payload["agent_work_preflight"]["status"] == "passed"
    assert (tmp_path / "preflight" / "preflight-report.json").exists()
    assert (tmp_path / "preflight" / "preflight-report.md").exists()


def test_live_apply_is_refused_without_apply(tmp_path: Path) -> None:
    split_plan = taskstream.build_fixture_split_plan(tmp_path / "fixture", base_commit="abc123")
    taskstream.emit_taskstream_manifests(split_plan_path=split_plan, out_dir=tmp_path / "fixture", run_preflight=False)

    args = argparse.Namespace(
        manifest_dir=str(tmp_path / "fixture" / "work-packages"),
        out=str(tmp_path / "live-refusal"),
        transport="agent-work",
        apply=False,
    )
    payload, code = taskstream.run_apply_from_args(args)

    assert code != 0
    assert payload["ok"] is False
    assert "requires explicit --apply" in payload["errors"][0]
    assert (tmp_path / "live-refusal" / "apply-refusal.json").exists()


def test_apply_path_uses_agent_work_command_preview_not_direct_db(tmp_path: Path) -> None:
    split_plan = taskstream.build_fixture_split_plan(tmp_path / "fixture", base_commit="abc123")
    taskstream.emit_taskstream_manifests(split_plan_path=split_plan, out_dir=tmp_path / "fixture", run_preflight=False)

    command_path = tmp_path / "fixture" / "work-packages" / "task-src-helper" / "agent-work-command.txt"
    command = command_path.read_text(encoding="utf-8")

    assert "cento agent-work create" in command
    assert "--manifest" in command
    forbidden = ["sqlite", "INSERT INTO", "UPDATE stories", "UPDATE issues", "redmine.db", "taskstream.db"]
    assert not any(item in command for item in forbidden)


def test_emit_rejects_unsafe_split_plan_paths(tmp_path: Path) -> None:
    split_plan = taskstream.build_fixture_split_plan(tmp_path / "fixture", base_commit="abc123")
    payload = read_json(split_plan)
    payload["tasks"][0]["owned_paths"] = ["../secrets.txt"]
    split_plan.write_text(taskstream.stable_json_dumps(payload), encoding="utf-8")

    args = argparse.Namespace(
        split_plan=str(split_plan),
        out=str(tmp_path / "fixture"),
        transport="manifest-only",
        run_preflight=False,
        default_route="agent-work",
    )
    payload, code = taskstream.run_emit_from_args(args)

    assert code != 0
    assert payload["ok"] is False
    assert "traversal" in payload["errors"][0]
