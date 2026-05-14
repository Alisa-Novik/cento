from __future__ import annotations

import json
from pathlib import Path

import sys


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import parallel_delivery_call_a as call_a  # noqa: E402
import parallel_delivery_validation_e2e as e2e  # noqa: E402


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_integration_conflict_triage_buckets_same_path_conflicts(tmp_path: Path) -> None:
    accepted = [
        {"task_id": "task-a", "bundle_id": "bundle-a", "path": "patch-bundles/a.json", "changed_paths": ["src/shared.py"]},
        {"task_id": "task-b", "bundle_id": "bundle-b", "path": "patch-bundles/b.json", "changed_paths": ["src/shared.py"]},
        {"task_id": "task-c", "bundle_id": "bundle-c", "path": "patch-bundles/c.json", "changed_paths": ["src/other.py"]},
    ]
    rejected = [
        {
            "task_id": "task-d",
            "bundle_id": "bundle-d",
            "path": "patch-bundles/d.json",
            "changed_paths": ["../secret.txt"],
            "errors": ["changed path outside owned lease"],
        }
    ]
    graph = {
        "run_id": "conflict-fixture",
        "created_at": "2026-01-01T00:00:00Z",
        "topological_order": ["task-a", "task-b", "task-c", "task-d"],
    }

    plan = e2e.create_integration_plan(tmp_path, accepted, rejected, graph)

    assert plan["bucket_counts"]["safe_apply"] == 1
    assert plan["bucket_counts"]["needs_human_review"] == 2
    assert plan["bucket_counts"]["reject"] == 1
    assert plan["conflict_count"] == 1
    assert [item["bundle_id"] for item in plan["queue"]] == ["bundle-c"]
    assert (tmp_path / "integration" / "integration-plan.json").exists()
    report = (tmp_path / "integration" / "conflict-report.md").read_text(encoding="utf-8")
    assert "Needs Human Review" in report
    assert "bundle-a" in report
    assert "bundle-b" in report
    assert "bundle-d" in report


def test_fixture_e2e_writes_conflict_report_and_buckets(tmp_path: Path) -> None:
    result = e2e.run_fixture_e2e(
        e2e.E2ERequest(
            run_id="call-a-e2e",
            run_root=tmp_path,
            candidate_target=5,
            max_parallel_agents=5,
            fixture=True,
            dry_run=True,
            fixed_timestamp="2026-01-01T00:00:00Z",
        )
    )

    assert result.ok, result.errors
    plan = read_json(result.run_dir / "integration" / "integration-plan.json")
    receipt = read_json(result.run_dir / "integration" / "integration-receipt.json")
    assert (result.run_dir / "integration" / "conflict-report.md").exists()
    assert plan["bucket_counts"]["safe_apply"] == 5
    assert plan["bucket_counts"]["reject"] == 1
    assert plan["conflict_count"] == 0
    assert receipt["bucket_counts"]["safe_apply"] == 5


def test_safety_fixture_detects_guards_and_classifies_console_diff(tmp_path: Path) -> None:
    diff = """
diff --git a/scripts/agent_work_app.py b/scripts/agent_work_app.py
+def patch_swarm_product_action_gates():
+    return {"can_apply": False}
"""
    checklist = call_a.write_safety_fixture(tmp_path, console_diff_text=diff)

    assert checklist["status"] == "passed"
    checks = {item["id"]: item for item in checklist["checks"]}
    assert checks["secret-paths-rejected"]["status"] == "passed"
    assert checks["absolute-and-traversal-paths-rejected"]["status"] == "passed"
    assert checks["unsafe-git-commands-detected"]["status"] == "passed"
    assert checks["direct-db-mutation-detected"]["status"] == "passed"
    assert checklist["console_review"]["classification"] == "patch_swarm_console"
    assert (tmp_path / "safety-checklist.json").exists()
    assert (tmp_path / "safety-report.md").exists()
    assert (tmp_path / "console-dirty-review.md").exists()
