from __future__ import annotations

import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import factory as factory_tool  # noqa: E402
import factory_dispatch_core as factory_dispatch  # noqa: E402
import factory_integration_e2e as integration_fixture  # noqa: E402
import factory_integrator_core as integrator  # noqa: E402


def prepare_factory_fixture(tmp_path: Path) -> Path:
    run_dir = tmp_path / "factory-fanout"
    patch_specs = integration_fixture.create_run(run_dir)
    factory_tool.materialize_run(run_dir)
    factory_dispatch.generate_queue(run_dir)
    integration_fixture.create_patch_bundles(run_dir, patch_specs)
    return run_dir


def test_factory_validate_fanout_caches_candidate_results(tmp_path: Path) -> None:
    run_dir = prepare_factory_fixture(tmp_path)

    first = integrator.validate_fanout(run_dir, max_parallel=4)
    second = integrator.validate_fanout(run_dir, max_parallel=4)

    assert first["schema_version"] == "factory-validation-fanout/v1"
    assert first["status"] == "passed"
    assert first["candidate_count"] == 3
    assert second["cache_hits"] == 3
    assert (run_dir / "integration" / "validation-cache").exists()
    assert (run_dir / "integration" / "validation-fanout-log.jsonl").exists()


def test_factory_merge_command_blocks_without_auto_ack(capsys) -> None:
    parser = factory_tool.build_parser()
    args = parser.parse_args(["merge", "workspace/runs/factory/example"])

    assert factory_tool.command_merge(args) == 2
    assert "requires --auto-merge-main" in capsys.readouterr().err


def test_factory_auto_merge_dry_run_blocks_dirty_or_wrong_branch(tmp_path: Path) -> None:
    run_dir = prepare_factory_fixture(tmp_path)
    integrator.prepare_branch(run_dir, dry_run=True, worktree=tmp_path / "integration-worktree")

    receipt = integrator.auto_merge_main(run_dir, dry_run=True)

    assert receipt["schema_version"] == "factory-auto-merge-receipt/v1"
    assert receipt["status"] == "blocked"
    assert receipt["dry_run"] is True
    assert receipt["push_requested"] is False
    assert "integration_worktree_missing" in receipt["blockers"]
    saved = json.loads((run_dir / "integration" / "merge-receipt.json").read_text(encoding="utf-8"))
    assert saved["status"] == "blocked"
