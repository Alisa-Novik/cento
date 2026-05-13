#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import parallel_delivery_artifacts as artifacts  # noqa: E402


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_TOOL = ROOT / "scripts" / "parallel_delivery_artifacts.py"
FIXED_TS = "2026-01-01T00:00:00Z"


def build_fixture(tmp_path: Path) -> Path:
    run_dir = tmp_path / "schema-fixture"
    artifacts.build_schema_fixture(run_dir, run_id="schema-fixture", timestamp=FIXED_TS)
    return run_dir


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    artifacts.write_json_artifact(path, payload)


def refresh_patch_bundle_manifest_hash(run_dir: Path) -> None:
    manifest_path = run_dir / "patch-bundles" / "manifest.json"
    manifest = read_json(manifest_path)
    bundle_path = run_dir / "patch-bundles" / "task-0001.bundle.json"
    manifest["bundles"][0]["sha256"] = artifacts.sha256_file(bundle_path)
    write_json(manifest_path, manifest)


def test_valid_fixture_validates_successfully(tmp_path: Path) -> None:
    run_dir = build_fixture(tmp_path)

    report = artifacts.validate_run_directory(run_dir)

    assert report["ok"] is True
    assert report["run_id"] == "schema-fixture"
    assert report["errors"] == []


def test_stable_json_serialization_is_deterministic() -> None:
    payload = {"b": 2, "a": {"d": 4, "c": 3}}

    assert artifacts.stable_json_dumps(payload) == '{\n  "a": {\n    "c": 3,\n    "d": 4\n  },\n  "b": 2\n}\n'
    assert artifacts.stable_json_dumps(payload) == artifacts.stable_json_dumps({"a": {"c": 3, "d": 4}, "b": 2})


def test_missing_required_field_fails_clearly(tmp_path: Path) -> None:
    run_dir = build_fixture(tmp_path)
    run = read_json(run_dir / "run.json")
    del run["request_title"]

    errors = artifacts.validate_run_artifact(run)

    assert any("missing required field request_title" in error for error in errors)


def test_invalid_schema_version_fails_and_future_can_be_allowed() -> None:
    assert artifacts.validate_schema_version({"schema_version": "1"})
    assert artifacts.validate_schema_version({"schema_version": 2})
    assert artifacts.validate_schema_version({"schema_version": 2}, allow_future=True) == []


def test_run_state_transitions_are_enforced() -> None:
    artifacts.validate_run_state_transition("request_received", "run_created")

    with pytest.raises(artifacts.ArtifactValidationError, match="invalid run state transition"):
        artifacts.validate_run_state_transition("completed", "run_created")


def test_task_state_transitions_are_enforced() -> None:
    artifacts.validate_task_state_transition("validation_passed", "queued_for_integration")

    with pytest.raises(artifacts.ArtifactValidationError, match="invalid task state transition"):
        artifacts.validate_task_state_transition("integrated", "rejected")


def test_max_candidate_tasks_over_100_is_rejected(tmp_path: Path) -> None:
    run_dir = build_fixture(tmp_path)
    split_plan = read_json(run_dir / "split-plan.json")
    split_plan["max_candidate_tasks"] = 101

    errors = artifacts.validate_split_plan(split_plan)

    assert any("max_candidate_tasks must be between 1 and 100" in error for error in errors)


def test_path_lease_parent_traversal_is_rejected(tmp_path: Path) -> None:
    run_dir = build_fixture(tmp_path)
    leases = read_json(run_dir / "path-leases.json")
    leases["leases"][0]["owned_paths"] = ["../outside.txt"]

    errors = artifacts.validate_path_leases(leases)

    assert any("parent traversal" in error for error in errors)


def test_path_lease_to_env_mcp_is_rejected(tmp_path: Path) -> None:
    run_dir = build_fixture(tmp_path)
    leases = read_json(run_dir / "path-leases.json")
    leases["leases"][0]["owned_paths"] = [".env.mcp"]

    errors = artifacts.validate_path_leases(leases)

    assert any(".env.mcp is not allowed" in error for error in errors)


def test_overlapping_active_leases_are_rejected(tmp_path: Path) -> None:
    run_dir = build_fixture(tmp_path)
    leases = read_json(run_dir / "path-leases.json")
    leases["leases"][1]["owned_paths"] = ["scripts/parallel_delivery_artifacts.py"]

    errors = artifacts.validate_path_leases(leases)

    assert any("active overlap" in error for error in errors)


def test_worker_ledger_invalid_json_line_reports_line_number(tmp_path: Path) -> None:
    ledger = tmp_path / "worker-ledger.jsonl"
    ledger.write_text('{"schema_version":1}\nnot-json\n', encoding="utf-8")

    errors = artifacts.validate_worker_ledger(ledger)

    assert any("line 2" in error and "invalid JSON" in error for error in errors)


def test_patch_bundle_changed_paths_outside_leased_paths_is_rejected(tmp_path: Path) -> None:
    run_dir = build_fixture(tmp_path)
    bundle_path = run_dir / "patch-bundles" / "task-0001.bundle.json"
    bundle = read_json(bundle_path)
    bundle["changed_paths"] = ["README.md"]
    bundle["claimed_paths"] = ["README.md"]
    write_json(bundle_path, bundle)
    refresh_patch_bundle_manifest_hash(run_dir)

    errors = artifacts.validate_patch_bundles(run_dir)

    assert any("outside leased paths" in error for error in errors)


def test_patch_bundle_changed_paths_outside_claimed_paths_is_rejected(tmp_path: Path) -> None:
    run_dir = build_fixture(tmp_path)
    bundle_path = run_dir / "patch-bundles" / "task-0001.bundle.json"
    bundle = read_json(bundle_path)
    bundle["changed_paths"] = ["scripts/parallel_delivery_artifacts.py"]
    bundle["claimed_paths"] = ["tests/test_parallel_delivery_artifact_schema.py"]
    write_json(bundle_path, bundle)
    refresh_patch_bundle_manifest_hash(run_dir)

    errors = artifacts.validate_patch_bundles(run_dir)

    assert any("outside claimed_paths" in error for error in errors)


def test_markdown_artifact_without_metadata_comment_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "request.md"
    path.write_text("# Request\n", encoding="utf-8")

    errors = artifacts.validate_markdown_artifact(path, "request", "schema-fixture")

    assert any("metadata comment" in error for error in errors)


def test_validate_run_json_cli_emits_parseable_json(tmp_path: Path) -> None:
    run_dir = build_fixture(tmp_path)

    result = subprocess.run(
        [sys.executable, str(SCHEMA_TOOL), "validate-run", "--run-dir", str(run_dir), "--json"],
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert payload["run_id"] == "schema-fixture"
