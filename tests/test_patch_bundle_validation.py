#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import parallel_delivery_patch_bundles as bundles  # noqa: E402


BASE_COMMIT = "abc123"


def write_fixture(root: Path) -> Path:
    bundles.build_fixture_inputs(root, base_commit=BASE_COMMIT, run_id="patch-bundle-fixture")
    return root


def validate(root: Path, name: str, *, run_id: str = "patch-bundle-fixture", base_commit: str = BASE_COMMIT) -> dict:
    receipt = bundles.validate_bundle_manifest(
        root / "input" / "bundles" / f"{name}.json",
        root / "input" / "leases.json",
        root,
        expected_run_id=run_id,
        expected_base_commit=base_commit,
        timestamp=bundles.DEFAULT_TIMESTAMP,
    )
    return bundles.receipt_to_dict(receipt)


def mutate_bundle(root: Path, name: str, update: dict) -> Path:
    source = root / "input" / "bundles" / "bundle-safe-001.json"
    payload = json.loads(source.read_text())
    payload.update(update)
    target = root / "input" / "bundles" / f"{name}.json"
    target.write_text(bundles.stable_json_dumps(payload))
    return target


def reason_codes(receipt: dict) -> set[str]:
    return set(receipt["reason_codes"])


def test_safe_patch_bundle_is_accepted(tmp_path: Path) -> None:
    root = write_fixture(tmp_path)
    receipt = validate(root, "bundle-safe-001")

    assert receipt["validation_status"] == "accepted"
    assert receipt["integratable"] is True
    assert receipt["reason_codes"] == []
    assert receipt["normalized_touched_paths"] == ["src/owned/example.py"]
    assert receipt["diff_paths"] == ["src/owned/example.py"]


def test_evidence_only_bundle_is_accepted_without_patch(tmp_path: Path) -> None:
    root = write_fixture(tmp_path)
    receipt = validate(root, "bundle-evidence-001")

    assert receipt["validation_status"] == "accepted"
    assert receipt["integratable"] is False
    assert receipt["patch_sha256"] is None
    assert receipt["reason_codes"] == []


def test_required_fixture_rejections_have_stable_reason_codes(tmp_path: Path) -> None:
    root = write_fixture(tmp_path)
    expected = {
        "bundle-outside-lease": {"path_outside_lease"},
        "bundle-protected-path": {"protected_path_edit", "local_secret_path_edit"},
        "bundle-env-mcp": {"protected_path_edit", "local_secret_path_edit"},
        "bundle-traversal": {"unsafe_path_traversal"},
        "bundle-absolute-path": {"absolute_path"},
        "bundle-symlink": {"symlink_patch_prohibited"},
        "bundle-submodule": {"submodule_patch_prohibited"},
        "bundle-binary": {"binary_patch_prohibited"},
        "bundle-undeclared-delete": {"undeclared_delete"},
        "bundle-unowned-rename": {"unowned_rename"},
        "bundle-broad-lockfile": {"broad_lockfile_change"},
        "bundle-secret-content": {"secret_like_content"},
    }

    for name, codes in expected.items():
        receipt = validate(root, name)
        assert receipt["validation_status"] == "rejected", name
        assert codes <= reason_codes(receipt), (name, receipt["reason_codes"])


def test_missing_required_field_and_invalid_schema_fail(tmp_path: Path) -> None:
    root = write_fixture(tmp_path)
    source = root / "input" / "bundles" / "bundle-safe-001.json"
    payload = json.loads(source.read_text())
    payload.pop("worker_id")
    payload["schema"] = "wrong.schema"
    bad = root / "input" / "bundles" / "bundle-invalid-schema.json"
    bad.write_text(bundles.stable_json_dumps(payload))

    receipt = validate(root, "bundle-invalid-schema")

    assert {"missing_required_field", "invalid_bundle_schema"} <= reason_codes(receipt)


def test_run_id_and_base_commit_mismatch_fail(tmp_path: Path) -> None:
    root = write_fixture(tmp_path)
    receipt = validate(root, "bundle-safe-001", run_id="different-run", base_commit="different-base")

    assert {"run_id_mismatch", "base_commit_mismatch"} <= reason_codes(receipt)


def test_missing_task_lease_fails(tmp_path: Path) -> None:
    root = write_fixture(tmp_path)
    mutate_bundle(root, "bundle-missing-lease", {"bundle_id": "bundle-missing-lease", "task_id": "task-missing"})

    receipt = validate(root, "bundle-missing-lease")

    assert "missing_task_lease" in reason_codes(receipt)


def test_diff_and_manifest_path_mismatch_fail(tmp_path: Path) -> None:
    root = write_fixture(tmp_path)
    mutate_bundle(
        root,
        "bundle-path-mismatch",
        {
            "bundle_id": "bundle-path-mismatch",
            "touched_paths": ["src/owned/declared-only.py"],
        },
    )

    receipt = validate(root, "bundle-path-mismatch")

    assert {"diff_path_not_declared", "declared_path_not_in_diff"} <= reason_codes(receipt)


def test_unsupported_patch_ref_fails(tmp_path: Path) -> None:
    root = write_fixture(tmp_path)
    mutate_bundle(
        root,
        "bundle-remote-ref",
        {
            "bundle_id": "bundle-remote-ref",
            "diff_path": "https://example.invalid/patch.diff",
        },
    )

    receipt = validate(root, "bundle-remote-ref")

    assert "unsupported_patch_ref" in reason_codes(receipt)


def test_unsafe_and_missing_evidence_refs_fail(tmp_path: Path) -> None:
    root = write_fixture(tmp_path)
    mutate_bundle(
        root,
        "bundle-bad-evidence",
        {
            "bundle_id": "bundle-bad-evidence",
            "result_status": "evidence_only",
            "touched_paths": [],
            "diff_path": None,
            "evidence_files": ["../secret-note.txt", "input/evidence/missing.txt"],
            "validation_commands": [],
        },
    )

    receipt = validate(root, "bundle-bad-evidence")

    assert {"unsafe_evidence_path", "missing_evidence_file"} <= reason_codes(receipt)


def test_worker_validation_missing_and_failed_are_rejected(tmp_path: Path) -> None:
    root = write_fixture(tmp_path)
    mutate_bundle(
        root,
        "bundle-missing-worker-validation",
        {"bundle_id": "bundle-missing-worker-validation", "validation_commands": []},
    )
    mutate_bundle(
        root,
        "bundle-failed-worker-validation",
        {"bundle_id": "bundle-failed-worker-validation", "validation_commands": [{"cmd": "false", "exit_code": 1}]},
    )

    missing = validate(root, "bundle-missing-worker-validation")
    failed = validate(root, "bundle-failed-worker-validation")

    assert "worker_validation_missing" in reason_codes(missing)
    assert "worker_validation_failed" in reason_codes(failed)
