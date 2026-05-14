from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import parallel_delivery_call_b as call_b  # noqa: E402
import parallel_delivery_prompts as prompts  # noqa: E402
import parallel_delivery_validation_e2e as e2e  # noqa: E402


ROOT = Path(__file__).resolve().parent.parent
FIXED_TS = "2026-01-01T00:00:00Z"
DISALLOWED_GENERATED_TEXT = [
    ".env.mcp",
    "OPENAI_API_KEY",
    "git reset --hard",
    "git clean -fd",
    "checkout --",
]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_fixture(tmp_path: Path, *, target: int = 5, max_agents: int = 5) -> Path:
    result = e2e.run_fixture_e2e(
        e2e.E2ERequest(
            run_id=f"regression-{target}",
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


def run_cento(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(ROOT / "scripts" / "cento.sh"), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=90,
    )


def test_regression_matrix_has_every_required_gate() -> None:
    matrix = call_b.build_regression_matrix("callB-test", generated_at=FIXED_TS)
    gate_ids = [item["id"] for item in matrix["gates"]]

    assert matrix["schema_version"] == "patch-swarm-regression-matrix.v1"
    assert gate_ids == call_b.REQUIRED_GATE_IDS
    assert all(item["live_external_dependencies"] is False for item in matrix["gates"])
    assert all(item["commands"] for item in matrix["gates"])


def test_docs_checklist_passes_for_current_runbook() -> None:
    checklist = call_b.docs_checklist("docs-check")

    assert checklist["schema_version"] == "patch-swarm-docs-checklist.v1"
    assert checklist["blockers"] == []
    assert set(checklist["required_sections"]) == set(call_b.DOC_SECTION_MARKERS)
    assert set(checklist["required_sections"].values()) == {"pass"}


def test_call_b_evidence_writer_summarizes_local_outputs(tmp_path: Path) -> None:
    regression_dir = tmp_path / "regression"
    docs_dir = tmp_path / "docs"
    output = regression_dir / "test-output"
    output.mkdir(parents=True)
    (output / "parallel-delivery-help.txt").write_text("parallel-delivery patch-swarm validate status\n", encoding="utf-8")
    (output / "parallel-delivery-validate.json").write_text('{"status":"passed"}\n', encoding="utf-8")
    (output / "parallel-delivery-status.json").write_text('{"status":"completed"}\n', encoding="utf-8")
    (output / "patch-swarm-e2e-100.json").write_text(
        '{"ok":true,"candidate_count":100,"max_parallel_agents":5,"live_pro":false}\n',
        encoding="utf-8",
    )
    (output / "pytest-test-patch-swarm.txt").write_text("15 passed in 1.0s\n", encoding="utf-8")
    (output / "pytest-focused-regression.txt").write_text("178 passed, 119 deselected in 20.0s\n", encoding="utf-8")
    (output / "tools-json-check.txt").write_text("{}\n", encoding="utf-8")
    (output / "cento-tools.txt").write_text("parallel-delivery\n", encoding="utf-8")

    result = call_b.write_evidence(regression_dir, docs_dir, run_id="callB-test")
    summary = read_json(regression_dir / "validation-summary.json")
    docs = read_json(docs_dir / "docs-checklist.json")

    assert result["ok"] is True
    assert summary["status"] == "pass"
    assert summary["gates"]["fixture-e2e-100"] == "pass"
    assert summary["gates"]["makefile-target"] in {"pass", "not-added", "not-applicable"}
    assert docs["blockers"] == []
    assert (regression_dir / "regression-matrix.md").exists()
    assert (docs_dir / "operator-runbook-review.md").exists()
    assert (docs_dir / "adoption-narrative.md").exists()


def test_cli_help_and_json_contracts() -> None:
    help_result = run_cento("parallel-delivery", "--help")
    assert help_result.returncode == 0, help_result.stderr
    assert "patch-swarm" in help_result.stdout
    assert "validate" in help_result.stdout
    assert "status" in help_result.stdout

    validate_result = run_cento("parallel-delivery", "validate", "--json")
    assert validate_result.returncode == 0, validate_result.stderr
    validate_payload = json.loads(validate_result.stdout)
    assert validate_payload["schema_version"]
    assert validate_payload["status"] in {"passed", "failed", "partial", "not_found"}
    assert "run_dir" in validate_payload

    status_result = run_cento("parallel-delivery", "status", "--json")
    assert status_result.returncode == 0, status_result.stderr
    status_payload = json.loads(status_result.stdout)
    assert status_payload["schema_version"]
    assert status_payload["status"]
    assert "run_kind" in status_payload


def test_fixture_artifact_schema_contract(tmp_path: Path) -> None:
    run_dir = run_fixture(tmp_path, target=5, max_agents=5)

    expected = {
        "run.json": {"schema_version", "run_id", "state", "candidate_count", "max_parallel_agents"},
        "split-plan.json": {"schema_version", "run_id", "candidate_count", "candidate_target", "tasks"},
        "task-graph.json": {"schema_version", "run_id", "nodes", "edges", "topological_order"},
        "path-leases.json": {"schema_version", "run_id", "leases", "conflicts", "parallel_groups"},
        "integration/integration-plan.json": {"schema_version", "run_id", "queue", "buckets", "bucket_counts", "rollback_metadata"},
        "validation-summary.json": {"schema_version", "run_id", "overall", "candidate_count", "simulated_worker_batches"},
        "release-candidate/release-candidate.json": {"schema_version", "run_id", "overall", "validation_summary", "integration_receipt"},
    }
    for relative, keys in expected.items():
        payload = read_json(run_dir / relative)
        assert keys <= set(payload), relative

    plan = read_json(run_dir / "integration" / "integration-plan.json")
    assert plan["bucket_counts"]["safe_apply"] == 5
    assert plan["bucket_counts"]["reject"] == 1
    assert (run_dir / "integration" / "conflict-report.md").exists()


def test_fixture_e2e_100_is_bounded_and_local(tmp_path: Path) -> None:
    run_dir = run_fixture(tmp_path, target=100, max_agents=5)
    summary = read_json(run_dir / "validation-summary.json")

    assert summary["overall"] == "passed"
    assert summary["candidate_count"] == 100
    assert summary["candidate_target"] == 100
    assert summary["max_parallel_agents"] == 5
    assert len(summary["simulated_worker_batches"]) == 20
    assert all(len(batch["task_ids"]) <= 5 for batch in summary["simulated_worker_batches"])
    assert summary["counts"]["accepted_patch_bundles"] == 100
    assert summary["counts"]["rejected_patch_bundles"] == 1


def test_generated_artifacts_do_not_contain_disallowed_instructions(tmp_path: Path) -> None:
    run_dir = tmp_path / "prompt-fixture"
    prompts.build_proreq_fixture(
        run_dir,
        count=15,
        lane="all",
        run_id="prompt-fixture",
        timestamp=FIXED_TS,
        temp_dir=tmp_path / "temp",
    )
    prompt_text = "\n".join(path.read_text(encoding="utf-8") for path in sorted((run_dir / "prompts").glob("*.md")))

    for token in DISALLOWED_GENERATED_TEXT:
        assert token not in prompt_text
    assert "## Mission" in prompt_text
    assert "## Owned Paths" in prompt_text
    assert "## Validation Plan" in prompt_text
    assert "## Evidence To Write" in prompt_text
    assert "## Safety Rules" in prompt_text
