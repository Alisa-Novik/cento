#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import parallel_delivery_taskstream as taskstream  # noqa: E402
import story_manifest  # noqa: E402
import validation_manifest  # noqa: E402


def build_split_plan(tmp_path: Path) -> tuple[taskstream.PatchSwarmSplitPlan, Path]:
    split_plan = taskstream.build_fixture_split_plan(tmp_path, base_commit="abc123")
    return taskstream.load_split_plan(split_plan), split_plan


def test_patch_swarm_task_maps_to_existing_agent_work_story_manifest(tmp_path: Path) -> None:
    plan, _ = build_split_plan(tmp_path)
    task = plan.tasks[0]
    story = taskstream.task_to_story_manifest(plan, task, out_dir=tmp_path, route="agent-work")

    errors = story_manifest.validate_manifest(story, check_links=False)
    assert errors == []
    assert story["schema"] == "cento.agent_work.story.v1"
    assert story["source"] == "parallel-delivery"
    assert story["task_id"] == "task-src-helper"
    assert story["issue"]["id"] == 0
    assert story["validation"]["manifest"].endswith("/validation.json")
    assert story["acceptance_contract"]


def test_patch_swarm_task_maps_to_existing_agent_work_validation_manifest(tmp_path: Path) -> None:
    plan, _ = build_split_plan(tmp_path)
    task = plan.tasks[0]
    story = taskstream.task_to_story_manifest(plan, task, out_dir=tmp_path, route="agent-work")
    story_path = tmp_path / "work-packages" / task.task_id / "story.json"
    validation = taskstream.task_to_validation_manifest(plan, task, story, story_path)

    errors = validation_manifest.validate_validation_manifest(validation)
    assert errors == []
    assert validation["schema"] == "cento.validation-manifest.v1"
    assert validation["compat_schema"] == "cento.agent_work.validation.v1"
    assert validation["source"] == "parallel-delivery"
    assert validation["task_id"] == "task-src-helper"
    assert validation["validation_commands"][0]["cmd"].startswith("python3")
    assert validation["expected_evidence_files"]


def test_manifest_only_task_can_have_no_task_validation_commands(tmp_path: Path) -> None:
    plan, _ = build_split_plan(tmp_path)
    task = plan.tasks[2]
    route = taskstream.choose_task_route(task)
    assert route == "manifest-only"

    story = taskstream.task_to_story_manifest(plan, task, out_dir=tmp_path, route=route)
    story_path = tmp_path / "work-packages" / task.task_id / "story.json"
    validation = taskstream.task_to_validation_manifest(plan, task, story, story_path)

    assert story_manifest.validate_manifest(story, check_links=False) == []
    assert validation_manifest.validate_validation_manifest(validation) == []
    assert validation["validation_commands"] == []
    assert validation["checks"][0]["name"] == "story-json-valid"


def test_invalid_story_and_validation_inputs_are_rejected(tmp_path: Path) -> None:
    plan, _ = build_split_plan(tmp_path)
    task = plan.tasks[0]

    missing_acceptance = taskstream.PatchSwarmTask(
        task_id=task.task_id,
        title=task.title,
        summary=task.summary,
        route="agent-work",
        worker_profile=task.worker_profile,
        priority=task.priority,
        owned_paths=task.owned_paths,
        touched_path_candidates=task.touched_path_candidates,
        acceptance_contract=[],
        validation_commands=task.validation_commands,
        evidence_files=task.evidence_files,
        handoff_notes=task.handoff_notes,
        risk_flags=task.risk_flags,
        lane=task.lane,
        risk_tier=task.risk_tier,
        state=task.state,
    )
    assert any(issue.field == "acceptance_contract" for issue in taskstream.validate_patch_swarm_task(missing_acceptance, route="agent-work"))

    missing_commands = taskstream.PatchSwarmTask(
        task_id=task.task_id,
        title=task.title,
        summary=task.summary,
        route="agent-work",
        worker_profile=task.worker_profile,
        priority=task.priority,
        owned_paths=task.owned_paths,
        touched_path_candidates=task.touched_path_candidates,
        acceptance_contract=task.acceptance_contract,
        validation_commands=[],
        evidence_files=task.evidence_files,
        handoff_notes=task.handoff_notes,
        risk_flags=task.risk_flags,
        lane=task.lane,
        risk_tier=task.risk_tier,
        state=task.state,
    )
    assert any(issue.field == "validation_commands" for issue in taskstream.validate_patch_swarm_task(missing_commands, route="agent-work"))


def test_unsafe_paths_are_rejected() -> None:
    unsafe = ["/tmp/story.json", "../story.json", "C:/Users/alice/.env", ".env.mcp", "workspace/../secret"]
    for path in unsafe:
        try:
            taskstream.normalize_safe_manifest_path(path)
        except taskstream.TaskstreamHandoffError:
            continue
        raise AssertionError(f"unsafe path was accepted: {path}")


def test_fixture_split_plan_has_required_tasks(tmp_path: Path) -> None:
    split_plan_path = taskstream.build_fixture_split_plan(tmp_path, base_commit="abc123")
    payload = json.loads(split_plan_path.read_text(encoding="utf-8"))
    assert payload["schema"] == "cento.parallel_delivery.split_plan.v1"
    assert [task["task_id"] for task in payload["tasks"]] == [
        "task-src-helper",
        "task-tests",
        "task-evidence-only",
    ]
