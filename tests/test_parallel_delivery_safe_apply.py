#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import parallel_delivery_release_candidate as rc  # noqa: E402


BASE_COMMIT = "fixture-base-commit"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_fixture(tmp_path: Path) -> Path:
    run_dir = tmp_path / "release-candidate-fixture"
    rc.build_release_candidate_fixture(run_dir, base_commit=BASE_COMMIT, timestamp="2026-01-01T00:00:00Z")
    return run_dir


def accepted_receipt(run_dir: Path) -> Path:
    return run_dir / "input" / "integration-receipt.accepted.json"


def test_accepted_integration_receipt_can_be_planned(tmp_path: Path) -> None:
    run_dir = build_fixture(tmp_path)
    receipt = rc.load_integration_receipt(accepted_receipt(run_dir))
    rc.assert_integration_receipt_accepted(receipt)

    plans = rc.load_and_verify_bundle_receipts(receipt, expected_base_commit=BASE_COMMIT)

    assert [plan.bundle_id for plan in plans] == ["bundle-safe-001", "bundle-safe-002"]
    assert all(plan.patch_path.exists() for plan in plans)


def test_rejected_integration_receipt_is_refused(tmp_path: Path) -> None:
    run_dir = build_fixture(tmp_path)
    receipt = rc.load_integration_receipt(run_dir / "input" / "integration-receipt.rejected.json")

    with pytest.raises(rc.ReleaseCandidateError, match="not accepted"):
        rc.assert_integration_receipt_accepted(receipt)


def test_rejected_bundle_receipt_is_refused_in_apply_order(tmp_path: Path) -> None:
    run_dir = build_fixture(tmp_path)
    path = accepted_receipt(run_dir)
    payload = read_json(path)
    payload["apply_order"] = ["bundle-safe-001", "bundle-rejected-001"]
    write_json(path, payload)
    receipt = rc.load_integration_receipt(path)

    with pytest.raises(rc.ReleaseCandidateError, match="rejected bundle"):
        rc.load_and_verify_bundle_receipts(receipt, expected_base_commit=BASE_COMMIT)


def test_non_integratable_bundle_receipt_is_refused(tmp_path: Path) -> None:
    run_dir = build_fixture(tmp_path)
    bundle = run_dir / "input" / "bundle-receipts" / "receipt-bundle-safe-001.json"
    payload = read_json(bundle)
    payload["integratable"] = False
    write_json(bundle, payload)
    receipt = rc.load_integration_receipt(accepted_receipt(run_dir))

    with pytest.raises(rc.ReleaseCandidateError, match="not integratable"):
        rc.load_and_verify_bundle_receipts(receipt, expected_base_commit=BASE_COMMIT)


def test_patch_hash_mismatch_is_refused(tmp_path: Path) -> None:
    run_dir = build_fixture(tmp_path)
    patch = run_dir / "input" / "patches" / "bundle-safe-001.diff"
    patch.write_text(patch.read_text(encoding="utf-8") + "\n# changed after receipt\n", encoding="utf-8")
    receipt = rc.load_integration_receipt(accepted_receipt(run_dir))

    with pytest.raises(rc.ReleaseCandidateError, match="sha256 mismatch"):
        rc.load_and_verify_bundle_receipts(receipt, expected_base_commit=BASE_COMMIT)


def test_dry_run_does_not_apply_patch_and_writes_rollback_metadata(tmp_path: Path) -> None:
    run_dir = build_fixture(tmp_path)
    source = run_dir / "fixture-repo" / "src" / "example.py"

    report = rc.create_release_candidate(
        integration_receipt_path=accepted_receipt(run_dir),
        out_dir=run_dir / "dry-run",
        mode="dry-run",
        target_repo=run_dir / "fixture-repo",
        expected_base_commit=BASE_COMMIT,
    )

    assert report["status"] == "dry_run_succeeded"
    assert report["applied_bundle_count"] == 0
    assert 'return "hello"\n' in source.read_text(encoding="utf-8")
    rollback = read_json(run_dir / "dry-run" / "rollback-metadata.json")
    assert rollback["rollback_strategy"] == "dry_run_no_changes"
    assert rollback["destructive_commands_used"] is False


def test_apply_stops_on_first_patch_failure(tmp_path: Path) -> None:
    run_dir = build_fixture(tmp_path)
    patch = run_dir / "input" / "patches" / "bundle-safe-002.diff"
    patch.write_text(
        "diff --git a/tests/test_example.py b/tests/test_example.py\n"
        "--- a/tests/test_example.py\n"
        "+++ b/tests/test_example.py\n"
        "@@ -99,1 +99,1 @@\n"
        "-missing\n"
        "+still-missing\n",
        encoding="utf-8",
    )
    receipt_path = run_dir / "input" / "bundle-receipts" / "receipt-bundle-safe-002.json"
    receipt = read_json(receipt_path)
    receipt["patch_sha256"] = rc.sha256_file(patch)
    write_json(receipt_path, receipt)

    report = rc.create_release_candidate(
        integration_receipt_path=accepted_receipt(run_dir),
        out_dir=run_dir / "apply-failure",
        mode="apply",
        target_repo=run_dir / "fixture-repo",
        target_worktree=run_dir / "integration-worktree-failure",
        expected_base_commit=BASE_COMMIT,
    )

    assert report["status"] == "failed"
    assert report["failed_bundle_id"] == "bundle-safe-002"
    assert report["applied_bundle_count"] == 1
    assert not (run_dir / "apply-failure" / "release-candidate.json").exists()
    rollback = read_json(run_dir / "apply-failure" / "rollback-metadata.json")
    assert rollback["failed_bundle_id"] == "bundle-safe-002"


def test_apply_stops_on_first_bundle_validation_failure(tmp_path: Path) -> None:
    run_dir = build_fixture(tmp_path)
    receipt_path = run_dir / "input" / "bundle-receipts" / "receipt-bundle-safe-002.json"
    receipt = read_json(receipt_path)
    receipt["validation_commands"] = [{"cmd": "python3 -c 'raise SystemExit(3)'"}]
    write_json(receipt_path, receipt)

    report = rc.create_release_candidate(
        integration_receipt_path=accepted_receipt(run_dir),
        out_dir=run_dir / "validation-failure",
        mode="apply",
        target_repo=run_dir / "fixture-repo",
        target_worktree=run_dir / "integration-worktree-validation",
        expected_base_commit=BASE_COMMIT,
    )

    assert report["status"] == "failed"
    assert report["failed_bundle_id"] == "bundle-safe-002"
    assert read_json(run_dir / "validation-failure" / "rollback-metadata.json")["failure_reason"] == "bundle_validation_failed"
