from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import parallel_delivery_validation_e2e as e2e  # noqa: E402


ROOT = Path(__file__).resolve().parent.parent
FIXED_TS = "2026-01-01T00:00:00Z"
REPORT_SECTIONS = [
    "## Summary",
    "## Fixture Configuration",
    "## Artifact Checks",
    "## Lease Checks",
    "## Worker Packet Checks",
    "## Patch Bundle Checks",
    "## Unsafe Bundle Rejection",
    "## Integration Plan",
    "## Dry-Run Integration Receipt",
    "## Release Candidate",
    "## Result",
]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_fixture(tmp_path: Path, *, run_id: str, target: int, max_agents: int) -> Path:
    result = e2e.run_fixture_e2e(
        e2e.E2ERequest(
            run_id=run_id,
            run_root=tmp_path,
            candidate_target=target,
            max_parallel_agents=max_agents,
            fixture=True,
            dry_run=True,
            fixed_timestamp=FIXED_TS,
        )
    )
    assert result.ok, result.errors
    return result.run_dir


def test_fixture_e2e_with_5_candidate_tasks_passes(tmp_path: Path) -> None:
    run_dir = run_fixture(tmp_path, run_id="fixture-5-workers", target=5, max_agents=5)
    summary = read_json(run_dir / "validation-summary.json")

    assert summary["overall"] == "passed"
    assert summary["candidate_count"] == 5
    assert summary["counts"]["candidate_tasks"] == 5
    assert summary["counts"]["accepted_patch_bundles"] == 5
    assert summary["counts"]["rejected_patch_bundles"] == 1
    for artifact in [
        "request.md",
        "run.json",
        "context-pack.json",
        "split-plan.json",
        "task-graph.json",
        "path-leases.json",
        "worker-packets/codex-packet-bundle.json",
        "worker-packets/codex-packet-index.json",
        "validation/patch-bundle-validation.json",
        "validation/malformed-artifact-validation.json",
        "integration/integration-plan.json",
        "integration/integration-receipt.json",
        "release-candidate/release-candidate.json",
        "release-candidate/release-notes.md",
        "command-output.log",
        "start-here.md",
    ]:
        assert (run_dir / artifact).exists(), artifact


def test_fixture_e2e_with_100_candidates_and_5_simulated_workers_passes(tmp_path: Path) -> None:
    run_dir = run_fixture(tmp_path, run_id="fixture-100-agents", target=100, max_agents=5)
    summary = read_json(run_dir / "validation-summary.json")
    split_plan = read_json(run_dir / "split-plan.json")
    leases = read_json(run_dir / "path-leases.json")
    packets = read_json(run_dir / "worker-packets" / "codex-packet-index.json")

    assert summary["overall"] == "passed"
    assert summary["candidate_count"] == 100
    assert summary["max_parallel_agents"] == 5
    assert len(split_plan["tasks"]) == 100
    assert len(leases["leases"]) == 100
    assert len(packets["packets"]) == 100
    assert summary["counts"]["accepted_patch_bundles"] == 100
    assert summary["counts"]["rejected_patch_bundles"] == 1
    assert len(summary["simulated_worker_batches"]) == 20
    assert all(len(batch["task_ids"]) <= 5 for batch in summary["simulated_worker_batches"])


def test_leases_do_not_overlap_and_every_task_is_batched_once(tmp_path: Path) -> None:
    run_dir = run_fixture(tmp_path, run_id="lease-batch-check", target=100, max_agents=5)
    summary = read_json(run_dir / "validation-summary.json")
    split_plan = read_json(run_dir / "split-plan.json")
    leases = read_json(run_dir / "path-leases.json")
    task_ids = {task["task_id"] for task in split_plan["tasks"]}

    assert {lease["task_id"] for lease in leases["leases"]} == task_ids
    owned: list[tuple[str, str]] = []
    for lease in leases["leases"]:
        for path in lease["owned_paths"]:
            owned.append((lease["task_id"], path.rstrip("/")))
    for index, (task_a, path_a) in enumerate(owned):
        for task_b, path_b in owned[index + 1 :]:
            assert not (path_a == path_b or path_a.startswith(path_b + "/") or path_b.startswith(path_a + "/")), (
                task_a,
                task_b,
            )

    seen: list[str] = []
    for batch in summary["simulated_worker_batches"]:
        seen.extend(batch["task_ids"])
    assert set(seen) == task_ids
    assert len(seen) == len(set(seen))


def test_unsafe_out_of_lease_bundle_and_malformed_artifact_are_rejected(tmp_path: Path) -> None:
    run_dir = run_fixture(tmp_path, run_id="negative-checks", target=5, max_agents=5)
    rejected = read_json(run_dir / "integration" / "rejected-patches.json")
    patch_validation = read_json(run_dir / "validation" / "patch-bundle-validation.json")
    malformed = read_json(run_dir / "validation" / "malformed-artifact-validation.json")

    rejected_text = json.dumps(rejected).lower()
    validation_text = json.dumps(patch_validation).lower()
    malformed_text = json.dumps(malformed).lower()

    assert "unsafe-out-of-lease" in rejected_text
    assert "changed path outside owned lease" in rejected_text
    assert "unsafe-out-of-lease" in validation_text
    assert malformed["ok"] is True
    assert "missing-run-id" in malformed_text or "run_id" in malformed_text
    assert "rejected" in malformed_text


def test_integration_plan_and_dry_run_receipt_exclude_rejected_bundle(tmp_path: Path) -> None:
    run_dir = run_fixture(tmp_path, run_id="integration-check", target=5, max_agents=5)
    plan = read_json(run_dir / "integration" / "integration-plan.json")
    receipt = read_json(run_dir / "integration" / "integration-receipt.json")

    assert len(plan["queue"]) == 5
    assert "unsafe-out-of-lease" not in json.dumps(plan["queue"])
    assert receipt["dry_run"] is True
    assert receipt["final_state"] == "dry_run_completed"
    assert len(receipt["integrated"]) == 5
    assert "unsafe-out-of-lease" not in json.dumps(receipt["integrated"])


def test_validation_report_sections_and_validate_existing_run(tmp_path: Path) -> None:
    run_dir = run_fixture(tmp_path, run_id="report-check", target=5, max_agents=5)
    text = (run_dir / "validation-report.md").read_text(encoding="utf-8")
    for section in REPORT_SECTIONS:
        assert section in text

    validation = e2e.validate_e2e_run(run_dir)
    assert validation["ok"] is True
    assert validation["overall"] == "passed"


def test_policy_is_local_only_and_no_live_calls() -> None:
    policy = e2e.print_policy()

    assert policy["schema_version"] == 1
    assert policy["local_only"] is True
    assert policy["no_api_calls"] is True
    assert policy["dry_run_integration"] is True
    assert policy["applies_patches"] is False
    assert policy["max_candidate_tasks"] == 100


def test_cli_json_output_is_parseable_and_stable(tmp_path: Path) -> None:
    run_root = tmp_path / "e2e-fixture"
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "parallel_delivery.py"),
        "patch-swarm",
        "e2e",
        "--candidate-target",
        "5",
        "--max-parallel-agents",
        "5",
        "--fixture",
        "--run-id",
        "cli-json",
        "--run-root",
        str(run_root),
        "--fixed-timestamp",
        FIXED_TS,
        "--json",
    ]
    first = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    second = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    first_payload = json.loads(first.stdout)
    second_payload = json.loads(second.stdout)
    assert first_payload == second_payload
    assert first_payload["ok"] is True
    assert first_payload["fixture"] is True
    assert first_payload["dry_run"] is True
    assert first_payload["live_pro"] is False
    assert first_payload["candidate_count"] == 5
