#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import parallel_delivery as pd  # noqa: E402


ROOT = Path(__file__).resolve().parent.parent


def configure_train_root(monkeypatch, tmp_path: Path) -> Path:
    train_root = tmp_path / "train"
    monkeypatch.setattr(pd, "TRAIN_RUNS_ROOT", train_root)
    return train_root


def configure_factory_root(monkeypatch, tmp_path: Path) -> Path:
    factory_root = tmp_path / "factory"
    monkeypatch.setattr(pd, "FACTORY_RUNS_ROOT", factory_root)
    return factory_root


def write_fake_workset_receipt(tmp_path: Path, task_paths: dict[str, str]) -> Path:
    workset_dir = tmp_path / "workset-run"
    tasks = {}
    for task_id, changed_path in task_paths.items():
        task_dir = workset_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        patch = task_dir / "patch.diff"
        patch.write_text(f"diff --git a/{changed_path} b/{changed_path}\n--- a/{changed_path}\n+++ b/{changed_path}\n@@ -1 +1 @@\n-old\n+new\n", encoding="utf-8")
        patch_bundle = task_dir / "patch_bundle.json"
        patch_bundle.write_text(
            json.dumps(
                {
                    "schema_version": "cento.patch_bundle.v1",
                    "patch_file": str(patch),
                    "touched_paths": [changed_path],
                    "owned_paths": [changed_path],
                    "unowned_paths": [],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        validation = task_dir / "validation_receipt.json"
        validation.write_text(json.dumps({"schema_version": "cento.validation_receipt.v1", "status": "passed"}) + "\n", encoding="utf-8")
        tasks[task_id] = {
            "id": task_id,
            "worker_id": task_id,
            "status": "accepted",
            "patch_bundle": str(patch_bundle),
            "patch": str(patch),
            "validation_receipt": str(validation),
            "changed_paths": [changed_path],
            "errors": [],
        }
    receipt = workset_dir / "workset_receipt.json"
    receipt.write_text(
        json.dumps(
            {
                "schema_version": "cento.workset_receipt.v1",
                "workset_id": "fake-workset",
                "run_id": "fake-workset-run",
                "status": "completed",
                "total_cost_usd": 0.0,
                "tasks": tasks,
                "patch_bundles": [task["patch_bundle"] for task in tasks.values()],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return receipt


def prepare_completed_train(monkeypatch, tmp_path: Path) -> tuple[Path, Path]:
    train_root = configure_train_root(monkeypatch, tmp_path)
    factory_root = configure_factory_root(monkeypatch, tmp_path)
    run_dir = train_root / "train-promote"
    source = ROOT / "tests" / "fixtures" / "cento_workset" / "workset.execute.fixture.json"
    manifest = pd.build_train_artifacts(source, run_dir, max_parallel=3)
    queue = json.loads((run_dir / "integration_queue.json").read_text(encoding="utf-8"))
    task_paths = {item["task_id"]: item["write_paths"][0] for item in queue["items"]}
    workset_receipt = write_fake_workset_receipt(tmp_path, task_paths)
    for item in queue["items"]:
        item["status"] = "workset_integrated"
        item["workset_task_status"] = "accepted"
        item["workset_receipt"] = str(workset_receipt)
    pd.write_json(run_dir / "integration_queue.json", queue)
    receipt = pd.train_receipt_payload(run_dir, manifest, queue, status="workset_completed")
    receipt.update({"workset_pipeline": True, "workset_status": "completed", "workset_receipt": str(workset_receipt), "workset_total_cost_usd": 0.0})
    pd.write_json(run_dir / "train_receipt.json", receipt)
    pd.write_json(
        run_dir / "workset_execute_result.json",
        {
            "schema_version": "cento.parallel_integration_train.workset_execute_result.v1",
            "run_id": run_dir.name,
            "exit_code": 0,
            "payload": {"status": "completed", "workset_receipt": str(workset_receipt)},
        },
    )
    return run_dir, factory_root


def test_train_plan_writes_manifest_and_dependency_queue(monkeypatch, tmp_path: Path) -> None:
    train_root = configure_train_root(monkeypatch, tmp_path)
    run_dir = train_root / "train-valid"
    source = ROOT / "tests" / "fixtures" / "cento_workset" / "workset.valid.json"

    manifest = pd.build_train_artifacts(source, run_dir, max_parallel=10)
    queue = json.loads((run_dir / "integration_queue.json").read_text(encoding="utf-8"))

    assert manifest["schema_version"] == pd.SCHEMA_TRAIN
    assert manifest["status"] == "planned"
    assert manifest["max_parallel"] == 10
    assert queue["schema_version"] == pd.SCHEMA_TRAIN_QUEUE
    assert [item["task_id"] for item in queue["items"]] == ["cluster_notice", "tui_standard", "mcp_standard"]
    assert queue["items"][2]["depends_on"] == ["cluster_notice", "tui_standard"]
    assert (run_dir / "decision_report.md").exists()


def test_train_plan_blocks_overlapping_workset(monkeypatch, tmp_path: Path) -> None:
    train_root = configure_train_root(monkeypatch, tmp_path)
    run_dir = train_root / "train-overlap"
    source = ROOT / "tests" / "fixtures" / "cento_workset" / "workset.overlap.json"

    manifest = pd.build_train_artifacts(source, run_dir, max_parallel=2)
    queue = json.loads((run_dir / "integration_queue.json").read_text(encoding="utf-8"))

    assert manifest["status"] == "blocked"
    assert any(shard["status"] == "blocked" for shard in manifest["shards"])
    assert any("conflicts" in " ".join(item["blockers"]) for item in queue["items"])


def test_train_plan_propagates_blocked_dependencies(monkeypatch, tmp_path: Path) -> None:
    train_root = configure_train_root(monkeypatch, tmp_path)
    source = tmp_path / "blocked-dependency.json"
    source.write_text(
        json.dumps(
            {
                "schema_version": "cento.workset.v1",
                "id": "blocked_dependency",
                "tasks": [
                    {"id": "first", "task": "first", "write_paths": ["CLUSTER_NOTICE.md"], "depends_on": []},
                    {"id": "second", "task": "second", "write_paths": ["CLUSTER_NOTICE.md"], "depends_on": []},
                    {"id": "third", "task": "third", "write_paths": ["standards/tui.md"], "depends_on": ["second"]},
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    manifest = pd.build_train_artifacts(source, train_root / "train-deps", max_parallel=3)
    third = next(item for item in manifest["shards"] if item["task_id"] == "third")

    assert third["status"] == "blocked"
    assert "blocked dependency: second" in third["blockers"]


def test_train_run_and_integrate_are_simulated_and_dry_run(monkeypatch, tmp_path: Path) -> None:
    train_root = configure_train_root(monkeypatch, tmp_path)
    run_dir = train_root / "train-valid"
    source = ROOT / "tests" / "fixtures" / "cento_workset" / "workset.execute.fixture.json"
    pd.build_train_artifacts(source, run_dir, max_parallel=3)

    run_receipt = pd.simulate_train_workers(run_dir)
    queue_after_run = json.loads((run_dir / "integration_queue.json").read_text(encoding="utf-8"))
    integrate_receipt = pd.dry_run_train_integration(run_dir)
    queue_after_integrate = json.loads((run_dir / "integration_queue.json").read_text(encoding="utf-8"))

    assert run_receipt["status"] == "workers_simulated"
    assert all(item["status"] == "ready_for_integration" for item in queue_after_run["items"])
    assert integrate_receipt["status"] == "integration_planned"
    assert all(item["status"] == "integration_planned" for item in queue_after_integrate["items"])
    assert all(item["apply"] is False for item in queue_after_integrate["items"])
    assert (run_dir / "workers" / "alpha" / "worker_receipt.json").exists()
    assert (run_dir / "integration" / "alpha" / "integration_receipt.json").exists()


def test_train_run_can_execute_parallel_workset_pipeline(monkeypatch, tmp_path: Path, capsys) -> None:
    train_root = configure_train_root(monkeypatch, tmp_path)
    run_dir = train_root / "train-workset"
    source = ROOT / "tests" / "fixtures" / "cento_workset" / "workset.execute.fixture.json"
    pd.build_train_artifacts(source, run_dir, max_parallel=3)
    calls: list[list[str]] = []

    def fake_run(command, **_kwargs):
        calls.append(command)
        return argparse.Namespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "status": "completed",
                    "workset_id": "workset_execute_fixture_001",
                    "run_id": "workset-run-1",
                    "workset_dir": ".cento/worksets/workset-run-1",
                    "workset_receipt": ".cento/worksets/workset-run-1/workset_receipt.json",
                    "task_statuses": {"alpha": "accepted", "beta": "accepted", "gamma": "accepted"},
                    "total_cost_usd": 0.0,
                    "changed_paths": [],
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(pd.subprocess, "run", fake_run)

    args = argparse.Namespace(
        run_id="train-workset",
        simulate=False,
        workset_execute=True,
        runtime="fixture",
        runtime_profile="",
        api_profile="api-section-worker",
        api_config=str(ROOT / ".cento" / "api_workers.yaml"),
        budget_usd=None,
        max_budget_usd=None,
        validation="smoke",
        worker_timeout=None,
        retry_attempts=None,
        fixture_case="valid",
        allow_dirty_owned=True,
        allow_creates=False,
        json=True,
    )
    assert pd.command_train_run(args) == 0
    output = json.loads(capsys.readouterr().out)
    queue = json.loads((run_dir / "integration_queue.json").read_text(encoding="utf-8"))
    command_record = json.loads((run_dir / "workset_execute_command.json").read_text(encoding="utf-8"))

    assert output["status"] == "workset_completed"
    assert output["workset_receipt"] == ".cento/worksets/workset-run-1/workset_receipt.json"
    assert calls[0][:4] == ["./scripts/cento.sh", "workset", "execute", str(run_dir / "workset.json")]
    assert "--apply" not in calls[0]
    assert "--allow-dirty-owned" in calls[0]
    assert all(item["status"] == "workset_integrated" for item in queue["items"])
    assert command_record["apply"] is False
    assert (run_dir / "workset_execute_result.json").exists()


def test_train_validate_requires_receipt(monkeypatch, tmp_path: Path) -> None:
    train_root = configure_train_root(monkeypatch, tmp_path)
    run_dir = train_root / "train-valid"
    source = ROOT / "tests" / "fixtures" / "cento_workset" / "workset.execute.fixture.json"
    pd.build_train_artifacts(source, run_dir, max_parallel=3)

    before = pd.validate_train_run(run_dir)
    pd.simulate_train_workers(run_dir)
    pd.dry_run_train_integration(run_dir)
    after = pd.validate_train_run(run_dir)

    assert before["status"] == "failed"
    assert after["status"] == "passed"


def test_train_promote_creates_factory_handoff_and_apply_plan(monkeypatch, tmp_path: Path) -> None:
    run_dir, factory_root = prepare_completed_train(monkeypatch, tmp_path)

    decision = pd.promote_train_run(run_dir)
    validation = pd.validate_train_run(run_dir)
    factory_run = factory_root / f"parallel-train-{run_dir.name}"
    apply_plan = json.loads((factory_run / "integration" / "apply-plan.json").read_text(encoding="utf-8"))

    assert decision["decision"] == "ready_for_apply"
    assert decision["status"] == "planned"
    assert (run_dir / "promotion_manifest.json").exists()
    assert (run_dir / "factory_handoff.json").exists()
    assert (run_dir / "promotion_decision.md").exists()
    assert (factory_run / "factory-plan.json").exists()
    assert (factory_run / "patch-collection-summary.json").exists()
    assert [item["task_id"] for item in apply_plan["candidates"]] == ["alpha", "beta", "gamma"]
    assert validation["status"] == "passed"


def test_train_promote_blocks_without_completed_workset(monkeypatch, tmp_path: Path) -> None:
    train_root = configure_train_root(monkeypatch, tmp_path)
    configure_factory_root(monkeypatch, tmp_path)
    run_dir = train_root / "train-blocked"
    source = ROOT / "tests" / "fixtures" / "cento_workset" / "workset.execute.fixture.json"
    pd.build_train_artifacts(source, run_dir, max_parallel=3)

    decision = pd.promote_train_run(run_dir)

    assert decision["status"] == "blocked"
    assert decision["decision"] == "blocked"
    assert "train status is unknown" in decision["blockers"]
    assert (run_dir / "promotion_decision.md").exists()


def test_train_cli_plan_status_and_validate(monkeypatch, tmp_path: Path, capsys) -> None:
    train_root = configure_train_root(monkeypatch, tmp_path)
    source = ROOT / "tests" / "fixtures" / "cento_workset" / "workset.execute.fixture.json"
    plan_args = argparse.Namespace(workset=str(source), max_parallel=3, run_id="train-cli", json=True)

    assert pd.command_train_plan(plan_args) == 0
    plan_output = json.loads(capsys.readouterr().out)
    assert plan_output["status"] == "planned"

    assert pd.command_train_run(argparse.Namespace(run_id="train-cli", simulate=True, json=True)) == 0
    capsys.readouterr()
    assert pd.command_train_integrate(argparse.Namespace(run_id="train-cli", dry_run=True, json=True)) == 0
    capsys.readouterr()
    assert pd.command_train_validate(argparse.Namespace(run_id="train-cli", json=True)) == 0
    capsys.readouterr()
    assert pd.command_train_status(argparse.Namespace(run_id="train-cli", json=True)) == 0
    status_output = json.loads(capsys.readouterr().out)
    assert status_output["run_dir"] == str(train_root / "train-cli")


def test_train_parser_exposes_subcommands() -> None:
    parser = pd.build_parser()
    args = parser.parse_args(["train", "plan", "--workset", "tests/fixtures/cento_workset/workset.valid.json"])
    run_args = parser.parse_args(["train", "run", "train-1", "--workset-execute", "--runtime", "fixture"])
    promote_args = parser.parse_args(["train", "promote", "train-1", "--dry-run"])
    e2e_args = parser.parse_args(["train", "e2e", "--workset", "tests/fixtures/cento_workset/workset.valid.json"])

    assert args.func == pd.command_train_plan
    assert run_args.func == pd.command_train_run
    assert run_args.workset_execute is True
    assert promote_args.func == pd.command_train_promote
    assert e2e_args.func == pd.command_train_e2e
