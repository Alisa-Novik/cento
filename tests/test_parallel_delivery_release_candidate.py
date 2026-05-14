#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import parallel_delivery_release_candidate as rc  # noqa: E402


ROOT = Path(__file__).resolve().parent.parent
BASE_COMMIT = "fixture-base-commit"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_fixture(tmp_path: Path, name: str = "release-candidate-fixture") -> Path:
    run_dir = tmp_path / name
    rc.build_release_candidate_fixture(run_dir, base_commit=BASE_COMMIT, timestamp="2026-01-01T00:00:00Z")
    return run_dir


def test_release_candidate_written_after_successful_apply_and_final_validation(tmp_path: Path) -> None:
    run_dir = build_fixture(tmp_path)

    report = rc.create_release_candidate(
        integration_receipt_path=run_dir / "input" / "integration-receipt.accepted.json",
        out_dir=run_dir / "apply",
        mode="apply",
        target_repo=run_dir / "fixture-repo",
        target_worktree=run_dir / "integration-worktree",
        expected_base_commit=BASE_COMMIT,
        final_validation_commands=["python3 -m pytest -q tests"],
    )

    assert report["status"] == "succeeded"
    assert report["release_candidate"] == "release-candidate.json"
    candidate = read_json(run_dir / "apply" / "release-candidate.json")
    assert candidate["schema"] == rc.SCHEMA_RELEASE_CANDIDATE
    assert candidate["status"] == "ready"
    assert candidate["bundle_ids"] == ["bundle-safe-001", "bundle-safe-002"]
    assert (run_dir / "apply" / "release-notes.md").exists()
    assert (run_dir / "apply" / "integrated.diff").exists()


def test_release_candidate_not_ready_when_final_validation_fails(tmp_path: Path) -> None:
    run_dir = build_fixture(tmp_path)

    report = rc.create_release_candidate(
        integration_receipt_path=run_dir / "input" / "integration-receipt.accepted.json",
        out_dir=run_dir / "final-validation-failure",
        mode="apply",
        target_repo=run_dir / "fixture-repo",
        target_worktree=run_dir / "integration-worktree-final-failure",
        expected_base_commit=BASE_COMMIT,
        final_validation_commands=["python3 -c 'raise SystemExit(2)'"],
    )

    assert report["status"] == "final_validation_failed"
    assert report["release_candidate"] is None
    assert not (run_dir / "final-validation-failure" / "release-candidate.json").exists()
    rollback = read_json(run_dir / "final-validation-failure" / "rollback-metadata.json")
    assert rollback["failure_reason"] == "final_validation_failed"


def test_parallel_delivery_release_candidate_cli_json_emits_valid_json(tmp_path: Path) -> None:
    run_dir = build_fixture(tmp_path, "cli-fixture")
    proc = subprocess.run(
        [
            str(ROOT / "scripts" / "cento.sh"),
            "parallel-delivery",
            "release-candidate",
            "create",
            "--integration-receipt",
            str(run_dir / "input" / "integration-receipt.accepted.json"),
            "--out",
            str(run_dir / "dry-run"),
            "--mode",
            "dry-run",
            "--target-repo",
            str(run_dir / "fixture-repo"),
            "--base-commit",
            BASE_COMMIT,
            "--json",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["status"] == "dry_run_succeeded"
    assert payload["applied_bundle_count"] == 0
