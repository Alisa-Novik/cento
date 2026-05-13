#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import parallel_delivery_leases as leases  # noqa: E402


ROOT = Path(__file__).resolve().parent.parent
FIXED_TS = "2026-01-01T00:00:00Z"


def fixture_payload(git_status_text: str = "") -> dict:
    plan = leases._fixture_split_plan("lease-test", FIXED_TS)
    graph = leases._fixture_task_graph(plan)
    return leases.create_leases(plan, graph, git_status_text=git_status_text, timestamp=FIXED_TS)


def task(task_id: str, owned: list[str], read: list[str] | None = None, contract: list[str] | None = None) -> dict:
    return {
        "task_id": task_id,
        "title": task_id,
        "summary": f"{task_id} summary",
        "lane": "builder",
        "risk_tier": "medium",
        "owned_paths": owned,
        "read_only_paths": read or ["docs/patch-swarm.md"],
        "dependencies": [],
        "acceptance_contract": contract or ["Only owned paths are changed."],
        "validation_commands": ["python3 -m json.tool data/tools.json >/dev/null"],
    }


def plan_with(tasks: list[dict], run_id: str = "lease-test") -> dict:
    return {
        "schema_version": 1,
        "artifact_type": "split-plan",
        "run_id": run_id,
        "created_at": FIXED_TS,
        "updated_at": FIXED_TS,
        "provenance": {"producer": "test", "command": "test", "source": "test", "repo": "cento", "notes": []},
        "max_candidate_tasks": len(tasks),
        "candidate_target": len(tasks),
        "candidate_count": len(tasks),
        "max_parallel_agents": 3,
        "tasks": tasks,
        "evidence_pointers": [],
    }


def test_stable_lease_ids_are_deterministic() -> None:
    first = fixture_payload()
    second = fixture_payload()

    assert [lease["lease_id"] for lease in first["leases"]] == [lease["lease_id"] for lease in second["leases"]]


def test_non_conflicting_docs_only_tasks_pass() -> None:
    payload = leases.create_leases(
        plan_with(
            [
                task("task-0001", ["docs/lease-a.md"]),
                task("task-0002", ["docs/lease-b.md"]),
            ]
        ),
        None,
        git_status_text="",
        timestamp=FIXED_TS,
    )

    assert leases.validate_path_leases(payload) == []


def test_shared_read_only_files_pass() -> None:
    payload = fixture_payload()
    task_1 = next(lease for lease in payload["leases"] if lease["task_id"] == "task-0001")
    task_2 = next(lease for lease in payload["leases"] if lease["task_id"] == "task-0002")

    assert task_1["read_only_paths"] == task_2["read_only_paths"] == ["docs/patch-swarm.md"]
    assert leases.validate_path_leases(payload) == []


def test_exact_owned_path_overlap_fails() -> None:
    payload = leases.create_leases(
        plan_with(
            [
                task("task-0001", ["docs/conflict.md"]),
                task("task-0002", ["docs/conflict.md"]),
            ]
        ),
        None,
        git_status_text="",
        timestamp=FIXED_TS,
    )

    assert any("exact owned path overlap" in error or "owned path overlap" in error for error in leases.validate_path_leases(payload))


def test_parent_child_owned_path_overlap_fails() -> None:
    payload = leases.create_leases(
        plan_with(
            [
                task("task-0001", ["docs/lease-parent"]),
                task("task-0002", ["docs/lease-parent/child.md"]),
            ]
        ),
        None,
        git_status_text="",
        timestamp=FIXED_TS,
    )

    assert any("parent/child owned path overlap" in error for error in leases.validate_path_leases(payload))


def test_different_files_in_same_directory_pass() -> None:
    payload = leases.create_leases(
        plan_with(
            [
                task("task-0001", ["docs/same-dir-a.md"]),
                task("task-0002", ["docs/same-dir-b.md"]),
            ]
        ),
        None,
        git_status_text="",
        timestamp=FIXED_TS,
    )

    assert leases.validate_path_leases(payload) == []


def test_protected_secret_paths_fail() -> None:
    payload = leases.create_leases(
        plan_with([task("task-0001", [".env.mcp"])]),
        None,
        git_status_text="",
        timestamp=FIXED_TS,
    )

    assert any("protected" in error or ".env.mcp" in error for error in leases.validate_path_leases(payload))


def test_guarded_registry_path_is_high_risk_and_requires_review() -> None:
    payload = fixture_payload()
    lease = next(item for item in payload["leases"] if item["task_id"] == "task-0004")

    assert lease["guarded_paths"] == ["data/tools.json"]
    assert lease["risk_tier"] == "high"
    assert lease["requires_manual_review"] is True
    assert lease["requires_minimal_hunks"] is True


def test_lockfile_change_outside_explicit_contract_fails() -> None:
    payload = fixture_payload()
    lease = next(item for item in payload["leases"] if item["task_id"] == "task-0005")
    lease["contract_allows_lockfile"] = False
    operations = {
        "schema_version": 1,
        "artifact_type": "planned-operations",
        "operations": [
            {"task_id": "task-0005", "changed_paths": ["package-lock.json"], "lockfile_paths": ["package-lock.json"]}
        ],
    }

    assert any("lockfile change requires explicit" in error for error in leases.validate_planned_operations(payload, operations))


def test_unsafe_delete_outside_owned_paths_fails() -> None:
    payload = fixture_payload()
    operations = {
        "schema_version": 1,
        "artifact_type": "planned-operations",
        "operations": [{"task_id": "task-0001", "deleted_paths": ["docs/unowned.md"]}],
    }

    assert any("unsafe delete" in error or "outside owned" in error for error in leases.validate_planned_operations(payload, operations))


def test_unowned_rename_fails() -> None:
    payload = fixture_payload()
    operations = {
        "schema_version": 1,
        "artifact_type": "planned-operations",
        "operations": [{"task_id": "task-0001", "renames": [{"from": "docs/unowned.md", "to": "docs/also-unowned.md"}]}],
    }

    assert any("unowned rename" in error for error in leases.validate_planned_operations(payload, operations))


def test_binary_patch_metadata_fails() -> None:
    payload = fixture_payload()
    operations = {
        "schema_version": 1,
        "artifact_type": "planned-operations",
        "operations": [{"task_id": "task-0001", "binary_paths": ["workspace/runs/parallel-delivery/lease-fixture/task-work/image.png"]}],
    }

    assert any("binary patch" in error for error in leases.validate_planned_operations(payload, operations))


def test_broad_cleanup_path_fails() -> None:
    payload = fixture_payload()
    operations = {
        "schema_version": 1,
        "artifact_type": "planned-operations",
        "operations": [{"task_id": "task-0001", "changed_paths": ["."]}],
    }

    assert any("broad cleanup" in error for error in leases.validate_planned_operations(payload, operations))


def test_dirty_target_warning_marks_high_risk_and_minimal_hunks() -> None:
    payload = fixture_payload(" M data/tools.json\n")
    lease = next(item for item in payload["leases"] if item["task_id"] == "task-0004")

    assert lease["dirty_owned_paths"] == ["data/tools.json"]
    assert lease["risk_tier"] == "high"
    assert lease["requires_minimal_hunks"] is True
    assert any("preserve unrelated hunks" in item["message"] for item in payload["warnings"])


def test_dependency_gates_are_emitted_from_task_graph_dependencies() -> None:
    payload = fixture_payload()

    assert any(gate["before"] == ["task-0001"] and gate["after"] == ["task-0003"] for gate in payload["dependency_gates"])


def test_parallel_groups_exclude_dependent_tasks() -> None:
    payload = fixture_payload()
    group_by_task = {
        task_id: group["group_id"]
        for group in payload["parallel_groups"]
        for task_id in group["task_ids"]
    }

    assert group_by_task["task-0001"] != group_by_task["task-0003"]


def test_parallel_groups_allow_independent_read_only_sharing_tasks() -> None:
    payload = fixture_payload()
    group_by_task = {
        task_id: group["group_id"]
        for group in payload["parallel_groups"]
        for task_id in group["task_ids"]
    }

    assert group_by_task["task-0001"] == group_by_task["task-0002"]


def test_path_leases_json_validates() -> None:
    assert leases.validate_path_leases(fixture_payload()) == []


def test_lease_conflict_report_is_generated(tmp_path: Path) -> None:
    payload = leases.build_lease_fixture(tmp_path / "fixture", run_id="lease-fixture", timestamp=FIXED_TS)

    assert payload["ok"] is True
    assert (tmp_path / "fixture" / "lease-conflict-report.md").exists()


def test_cli_json_emits_valid_json(tmp_path: Path) -> None:
    run_dir = tmp_path / "cli-fixture"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "parallel_delivery.py"),
            "patch-swarm",
            "leases",
            "--run-dir",
            str(run_dir),
            "--run-id",
            "cli-lease-fixture",
            "--fixture",
            "--json",
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert (run_dir / "path-leases.json").exists()
