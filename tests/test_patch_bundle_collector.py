#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import parallel_delivery_patch_bundles as bundles  # noqa: E402


BASE_COMMIT = "abc123"
RUN_ID = "patch-bundle-fixture"
ROOT = Path(__file__).resolve().parent.parent


def test_collector_writes_receipts_and_aggregate_reports(tmp_path: Path) -> None:
    bundles.build_fixture_inputs(tmp_path, base_commit=BASE_COMMIT, run_id=RUN_ID)

    report = bundles.collect_patch_bundles(
        tmp_path / "input" / "bundles",
        tmp_path / "input" / "leases.json",
        tmp_path,
        run_id=RUN_ID,
        base_commit=BASE_COMMIT,
        timestamp=bundles.DEFAULT_TIMESTAMP,
    )

    assert report["schema"] == bundles.SCHEMA_REPORT
    assert report["run_id"] == RUN_ID
    assert report["accepted_count"] >= 2
    assert report["rejected_count"] >= 10
    assert report["evidence_only_count"] == 1
    assert (tmp_path / "patch-bundle-report.json").exists()
    assert (tmp_path / "patch-bundle-report.md").exists()
    assert (tmp_path / "validation-summary.txt").exists()
    receipts = sorted((tmp_path / "receipts").glob("*.json"))
    assert len(receipts) == report["receipt_count"]

    required = {
        "path_outside_lease",
        "protected_path_edit",
        "local_secret_path_edit",
        "unsafe_path_traversal",
        "absolute_path",
        "symlink_patch_prohibited",
        "submodule_patch_prohibited",
        "binary_patch_prohibited",
        "undeclared_delete",
        "unowned_rename",
        "broad_lockfile_change",
        "secret_like_content",
    }
    assert required <= set(report["rejection_reason_counts"])


def test_parallel_delivery_patch_bundles_collect_cli_emits_json(tmp_path: Path) -> None:
    bundles.build_fixture_inputs(tmp_path, base_commit=BASE_COMMIT, run_id=RUN_ID)

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "parallel_delivery.py"),
            "patch-bundles",
            "collect",
            "--run-id",
            RUN_ID,
            "--bundles-dir",
            str(tmp_path / "input" / "bundles"),
            "--lease-manifest",
            str(tmp_path / "input" / "leases.json"),
            "--out",
            str(tmp_path),
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

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["accepted_count"] >= 2
    assert payload["rejected_count"] >= 10
    assert (tmp_path / "patch-bundle-report.json").exists()


def test_fixture_script_writes_required_inputs(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "parallel_delivery" / "patch_bundle_fixture.py"),
            "--out",
            str(tmp_path),
            "--base-commit",
            BASE_COMMIT,
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["run_id"] == RUN_ID
    assert (tmp_path / "input" / "leases.json").exists()
    assert (tmp_path / "input" / "bundles" / "bundle-safe-001.json").exists()
    assert (tmp_path / "input" / "bundles" / "bundle-evidence-001.json").exists()
    assert (tmp_path / "input" / "patches" / "bundle-safe-001.diff").exists()
    assert (tmp_path / "input" / "evidence" / "worker-a-validation.txt").exists()
