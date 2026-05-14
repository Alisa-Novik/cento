from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import agent_work_app as app  # noqa: E402
import parallel_delivery as pd  # noqa: E402


def configure_patch_swarm_roots(monkeypatch, tmp_path: Path) -> Path:
    swarm_root = tmp_path / "parallel-delivery" / "patch-swarm"
    pipeline_root = tmp_path / "dev-pipeline-studio" / "latest"
    factory_root = tmp_path / "factory"
    monkeypatch.setattr(pd, "PATCH_SWARM_RUNS_ROOT", swarm_root)
    monkeypatch.setattr(pd, "PIPELINE_ROOT", pipeline_root)
    monkeypatch.setattr(pd, "FACTORY_RUNS_ROOT", factory_root)
    return swarm_root


def init_git_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "README.md").write_text("# Sample App\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=path, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(
        ["git", "-c", "user.email=test@example.com", "-c", "user.name=Test User", "commit", "-m", "init"],
        cwd=path,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return path


def test_patch_swarm_e2e_writes_100_candidates_and_one_integrator(monkeypatch, tmp_path: Path) -> None:
    swarm_root = configure_patch_swarm_roots(monkeypatch, tmp_path)
    run_dir = swarm_root / "patch-swarm-test"

    manifest = pd.build_patch_swarm_plan(run_dir, candidate_target=100, max_parallel_agents=5)
    receipt = pd.execute_patch_swarm(run_dir)
    integration = pd.integrate_patch_swarm(run_dir)
    validation = pd.validate_patch_swarm_run(run_dir)

    candidate_index = json.loads((run_dir / "candidate_index.json").read_text(encoding="utf-8"))
    proreq = json.loads((run_dir / "proreq_execution_manifest.json").read_text(encoding="utf-8"))

    assert manifest["schema_version"] == pd.SCHEMA_PATCH_SWARM
    assert manifest["proreq_execution_count"] == 10
    assert len(proreq["executions"]) == 10
    assert receipt["candidate_count"] == 100
    assert len(candidate_index["candidates"]) == 100
    assert {"codex-exec", "claude-code", "api-openai"} <= set(receipt["provider_counts"])
    assert integration["id"] == "dedicated-integrator"
    assert integration["selected_count"] == 10
    assert integration["apply"] is False
    assert validation["status"] == "passed"
    assert (run_dir / "safe_integrator_handoff.json").exists()
    assert (run_dir / "ui_state.json").exists()
    assert (tmp_path / "dev-pipeline-studio" / "latest" / "execution" / "patch-swarm" / "latest_ui_state.json").exists()


def test_patch_swarm_cli_e2e_json(monkeypatch, tmp_path: Path, capsys) -> None:
    swarm_root = configure_patch_swarm_roots(monkeypatch, tmp_path)
    args = argparse.Namespace(
        run_id="patch-swarm-cli",
        objective="Test patch swarm CLI",
        candidate_target=100,
        max_parallel_agents=5,
        providers="codex-exec,claude-code,api-openai",
        fixture=True,
        live=False,
        json=True,
    )

    assert pd.command_patch_swarm_e2e(args) == 0
    output = json.loads(capsys.readouterr().out)

    assert output["status"] == "completed"
    assert output["candidate_count"] == 100
    assert output["selected_count"] == 10
    assert output["run_dir"] == str(swarm_root / "patch-swarm-cli")


def test_patch_swarm_parser_exposes_subcommands() -> None:
    parser = pd.build_parser()
    plan = parser.parse_args(["patch-swarm", "plan", "--run-id", "swarm-1"])
    execute = parser.parse_args(["patch-swarm", "execute", "swarm-1", "--live", "--budget-cap", "1"])
    integrate = parser.parse_args(["patch-swarm", "integrate", "swarm-1", "--apply", "--factory-run", "workspace/tmp/factory"])
    e2e = parser.parse_args(["patch-swarm", "e2e", "--candidate-target", "100", "--apply", "--limit", "1"])

    assert plan.func == pd.command_patch_swarm_plan
    assert execute.func == pd.command_patch_swarm_execute
    assert execute.budget_cap_usd == 1
    assert integrate.func == pd.command_patch_swarm_integrate
    assert integrate.apply is True
    assert integrate.factory_run == "workspace/tmp/factory"
    assert e2e.func == pd.command_patch_swarm_e2e
    assert e2e.apply is True
    assert e2e.limit == 1


def test_patch_swarm_live_execution_is_budget_and_adapter_gated(monkeypatch, tmp_path: Path) -> None:
    swarm_root = configure_patch_swarm_roots(monkeypatch, tmp_path)
    run_dir = swarm_root / "patch-swarm-live-gate"
    pd.build_patch_swarm_plan(run_dir, candidate_target=100, max_parallel_agents=5, live=True)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    no_budget = pd.execute_patch_swarm(run_dir, fixture=False)
    capped = pd.execute_patch_swarm(run_dir, fixture=False, budget_cap_usd=1.0)

    assert no_budget["status"] == "blocked"
    assert "live execution requires --budget-cap-usd" in no_budget["errors"]
    assert capped["status"] == "blocked"
    assert "OPENAI_API_KEY is missing" in capped["errors"]
    assert (run_dir / "usage_guard.json").exists()


def test_patch_swarm_live_execution_blocks_when_estimated_cost_exceeds_cap(monkeypatch, tmp_path: Path) -> None:
    swarm_root = configure_patch_swarm_roots(monkeypatch, tmp_path)
    run_dir = swarm_root / "patch-swarm-live-budget"
    pd.build_patch_swarm_plan(run_dir, candidate_target=10, max_parallel_agents=2, live=True)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    receipt = pd.execute_patch_swarm(run_dir, fixture=False, budget_cap_usd=0.001, max_budget_usd=1.0)

    assert receipt["status"] == "blocked"
    assert "estimated provider spend exceeds budget cap" in receipt["errors"]


def test_patch_swarm_api_worker_artifact_converts_to_candidate_patch(monkeypatch, tmp_path: Path) -> None:
    swarm_root = configure_patch_swarm_roots(monkeypatch, tmp_path)
    run_dir = swarm_root / "patch-swarm-api-convert"
    manifest = pd.build_patch_swarm_plan(run_dir, candidate_target=10, max_parallel_agents=2, live=True)
    execution = json.loads((run_dir / "proreq_execution_manifest.json").read_text(encoding="utf-8"))["executions"][0]
    artifact_dir = run_dir / "proreq_executions" / execution["id"] / "candidates" / "api-cand-api-worker"
    artifact_dir.mkdir(parents=True)
    target_path = f"workspace/runs/parallel-delivery/patch-swarm/{run_dir.name}/api-sandbox/api-cand.md"
    pd.write_json(
        artifact_dir / "artifact.json",
        {
            "schema_version": "cento.api_worker_artifact.v1",
            "worker_id": "api-openai-api-cand",
            "task_id": "api-cand",
            "status": "completed",
            "artifact_type": "patch_proposal",
            "owned_paths": [target_path],
            "content": {
                "schema_version": "patch_proposal.v1",
                "summary": "Write a sandbox candidate.",
                "owned_path_contents": [{"path": target_path, "content": "# API sandbox candidate\n"}],
                "risks": [],
                "validation": ["git apply --check"],
            },
            "cost_usd_estimate": 0.0125,
            "errors": [],
        },
    )
    pd.write_json(artifact_dir / "cost_receipt.json", {"schema_version": "cento.api_worker_cost_receipt.v1", "cost_usd_estimate": 0.0125})
    worker_result = {
        "artifact": pd.rel(artifact_dir / "artifact.json"),
        "cost_receipt": pd.rel(artifact_dir / "cost_receipt.json"),
        "worker_receipt": pd.rel(artifact_dir / "worker_receipt.json"),
        "cost_usd_estimate": 0.0125,
    }
    proc = subprocess.CompletedProcess(args=[], returncode=0, stdout="{}", stderr="")

    candidate, validation = pd.patch_swarm_api_artifact_to_candidate(run_dir, execution, "api-cand", 1, artifact_dir, worker_result, proc)

    assert manifest["live_dispatch_enabled"] is True
    assert candidate["schema_version"] == pd.SCHEMA_PATCH_SWARM_CANDIDATE
    assert candidate["status"] == "validated"
    assert candidate["provider"] == "api-openai"
    assert validation["status"] == "passed"
    assert pd.resolve_cento_path(candidate["patch"]["patch_file"]).exists()


def test_patch_swarm_fixture_validation_includes_git_apply_check(monkeypatch, tmp_path: Path) -> None:
    swarm_root = configure_patch_swarm_roots(monkeypatch, tmp_path)
    run_dir = swarm_root / "patch-swarm-git-apply"
    pd.build_patch_swarm_plan(run_dir, candidate_target=10, max_parallel_agents=5)

    receipt = pd.execute_patch_swarm(run_dir)
    candidate_index = json.loads((run_dir / "candidate_index.json").read_text(encoding="utf-8"))
    validated = [item for item in candidate_index["candidates"] if item["status"] == "validated"]
    validation = json.loads(pd.resolve_cento_path(validated[0]["validation_receipt"]).read_text(encoding="utf-8"))

    assert receipt["status"] == "candidates_generated"
    assert validated
    assert {"name": "git_apply_check", "status": "passed", "stderr_tail": ""} in validation["checks"]


def test_patch_swarm_integrate_can_promote_winners_to_factory(monkeypatch, tmp_path: Path) -> None:
    swarm_root = configure_patch_swarm_roots(monkeypatch, tmp_path)
    run_dir = swarm_root / "patch-swarm-promote"
    factory_run = tmp_path / "factory" / "patch-swarm-promote-factory"
    pd.build_patch_swarm_plan(run_dir, candidate_target=100, max_parallel_agents=5)
    pd.execute_patch_swarm(run_dir)

    integration = pd.integrate_patch_swarm(run_dir, factory_run=str(factory_run))
    promotion = json.loads((run_dir / "factory_promotion.json").read_text(encoding="utf-8"))

    assert integration["status"] == "completed"
    assert integration["factory_promotion"] == pd.rel(run_dir / "factory_promotion.json")
    assert promotion["schema_version"] == "cento.patch_swarm.factory_promotion.v1"
    assert promotion["factory_run_dir"] == pd.rel(factory_run)
    assert (factory_run / "factory-plan.json").exists()
    assert (factory_run / "integration" / "apply-plan.json").exists()
    assert (factory_run / "integration" / "validation-fanout.json").exists()


def test_dev_pipeline_patch_swarm_blueprint_is_registered() -> None:
    template = app.dev_pipeline_patch_swarm_blueprint_defaults()
    project = app.dev_pipeline_patch_swarm_project_defaults()

    assert project["id"] == app.PATCH_SWARM_PROJECT_ID
    assert template["id"] == app.PATCH_SWARM_TEMPLATE_ID
    assert template["max_parallel"] == 5
    assert len(template["workers"]) == 10
    assert len(template["factory_steps"]) == 11
    assert template["factory_steps"][-1]["id"] == "dedicated-integrator"
    assert app.dev_pipeline_template_is_patch_swarm(template) is True


def test_patch_swarm_product_discovers_local_repos(monkeypatch, tmp_path: Path) -> None:
    repo = init_git_repo(tmp_path / "sample-app")
    monkeypatch.setenv("CENTO_PATCH_SWARM_REPO_ROOTS", str(tmp_path))

    payload = app.patch_swarm_discover_repos()

    assert any(item["path"] == str(repo.resolve()) for item in payload["repos"])
    assert payload["protected_policy"]["names"]


def test_patch_swarm_product_run_lifecycle_for_selected_repo(monkeypatch, tmp_path: Path) -> None:
    swarm_root = configure_patch_swarm_roots(monkeypatch, tmp_path)
    monkeypatch.setattr(app, "PATCH_SWARM_PRODUCT_WORKTREE_ROOT", tmp_path / "worktrees")
    repo = init_git_repo(tmp_path / "selected-app")
    before_create = app.patch_swarm_repo_snapshot(repo)

    detail = app.patch_swarm_product_create_run(
        {
            "run_id": "patch-swarm-product-test",
            "repo_path": str(repo),
            "task_brief": "Add a small supervised candidate file.",
            "candidate_target": 10,
            "max_parallel_agents": 2,
            "providers": "codex-exec,claude-code,api-openai",
        }
    )
    run_dir = swarm_root / "patch-swarm-product-test"
    after_create = app.patch_swarm_repo_snapshot(repo)

    assert detail["run_kind"] == "product"
    assert detail["run"]["run_kind"] == "product"
    assert detail["run"]["selected_repo"]["path"] == str(repo.resolve())
    assert detail["run"]["candidate_count"] == 10
    assert detail["run"]["selected_count"] == 10
    assert detail["run"]["validation"] == "passed"
    assert detail["action_gates"]["can_approve"] is True
    assert detail["action_gates"]["can_apply"] is False
    assert detail["action_gates"]["apply_disabled_reason"] == "approval required"
    assert (run_dir / "product_metadata.json").exists()
    assert (run_dir / "product_run_create_receipt.json").exists()
    assert detail["no_mutation"]["status"] == "passed"
    assert before_create["fingerprint"] == after_create["fingerprint"]
    assert detail["candidates"][0]["touched_paths"][0].startswith("patch-swarm-candidates/patch-swarm-product-test/")
    listed = app.patch_swarm_product_run_list()
    assert next(item for item in listed["runs"] if item["run_id"] == "patch-swarm-product-test")["run_kind"] == "product"

    rejected_id = detail["candidates"][-1]["id"]
    rejected = app.patch_swarm_product_reject("patch-swarm-product-test", {"candidate_ids": [rejected_id], "reason": "not this one"})
    assert rejected["candidates"][-1]["decision"] == "rejected"

    try:
        app.patch_swarm_product_apply("patch-swarm-product-test", {"limit": 1, "use_factory": False})
    except app.AgentWorkAppError as exc:
        assert "approval required" in str(exc)
    else:
        raise AssertionError("apply was accepted before approval")

    selected_id = detail["integration"]["selected_candidates"][0]
    approved = app.patch_swarm_product_approve("patch-swarm-product-test", {"candidate_ids": [selected_id]})
    assert approved["approval"]["status"] == "approved"
    assert approved["approval"]["selected_candidate_ids"] == [selected_id]
    assert approved["action_gates"]["can_approve"] is False
    assert approved["action_gates"]["can_apply"] is True

    try:
        app.patch_swarm_product_apply(
            "patch-swarm-product-test",
            {"limit": 1, "use_factory": False, "worktree": str(tmp_path / "outside-worktree")},
        )
    except app.AgentWorkAppError as exc:
        assert "non-product Patch Swarm worktree" in str(exc)
    else:
        raise AssertionError("external apply accepted a non-product worktree")

    before_apply = app.patch_swarm_repo_snapshot(repo)
    applied = app.patch_swarm_product_apply("patch-swarm-product-test", {"limit": 1, "use_factory": True})
    after_apply = app.patch_swarm_repo_snapshot(repo)
    receipt = applied["apply_receipt"]
    selected_candidate = next(item for item in applied["candidates"] if item["id"] == selected_id)
    touched_path = selected_candidate["touched_paths"][0]
    assert receipt["status"] == "applied"
    assert receipt["apply_scope"] == "product_worktree_only"
    assert Path(receipt["worktree"]).resolve().is_relative_to((tmp_path / "worktrees").resolve())
    assert Path(receipt["worktree"], touched_path).exists()
    assert not (repo / touched_path).exists()
    assert before_apply["fingerprint"] == after_apply["fingerprint"]
    assert applied["no_mutation"]["status"] == "passed"
    assert applied["action_gates"]["can_apply"] is False


def test_patch_swarm_product_blocks_protected_dirty_repo(monkeypatch, tmp_path: Path) -> None:
    configure_patch_swarm_roots(monkeypatch, tmp_path)
    repo = init_git_repo(tmp_path / "protected-dirty")
    (repo / ".env").write_text("TOKEN=test\n", encoding="utf-8")

    state = app.patch_swarm_repo_state(repo)
    assert ".env" in state["protected_dirty"]
    assert state["can_start"] is False
    assert state["safety_label"] == "blocked_protected_dirty"

    try:
        app.patch_swarm_product_create_run(
            {
                "run_id": "patch-swarm-protected-dirty",
                "repo_path": str(repo),
                "task_brief": "Try a protected dirty repo.",
                "candidate_target": 10,
            }
        )
    except app.AgentWorkAppError as exc:
        assert "protected dirty paths" in str(exc)
    else:
        raise AssertionError("protected dirty repo was accepted")


def test_patch_swarm_product_labels_unprotected_dirty_repo_startable(tmp_path: Path) -> None:
    repo = init_git_repo(tmp_path / "unprotected-dirty")
    (repo / "notes.txt").write_text("operator local note\n", encoding="utf-8")

    state = app.patch_swarm_repo_state(repo)

    assert state["dirty"] is True
    assert state["dirty_paths"] == ["notes.txt"]
    assert state["protected_dirty"] == []
    assert state["can_start"] is True
    assert state["safety_label"] == "startable_unprotected_dirty"


def test_patch_swarm_engine_runs_are_read_only_in_product_api(monkeypatch, tmp_path: Path) -> None:
    swarm_root = configure_patch_swarm_roots(monkeypatch, tmp_path)
    run_dir = swarm_root / "patch-swarm-engine-contract"
    pd.build_patch_swarm_plan(run_dir, candidate_target=10, max_parallel_agents=2)
    pd.execute_patch_swarm(run_dir)
    pd.integrate_patch_swarm(run_dir)
    pd.validate_patch_swarm_run(run_dir)

    detail = app.patch_swarm_product_run_detail("patch-swarm-engine-contract")
    listed = app.patch_swarm_product_run_list()

    assert detail["run_kind"] == "engine"
    assert detail["run"]["run_kind"] == "engine"
    assert detail["action_gates"]["can_approve"] is False
    assert detail["action_gates"]["approve_disabled_reason"] == "engine-only run"
    assert next(item for item in listed["runs"] if item["run_id"] == "patch-swarm-engine-contract")["run_kind"] == "engine"
    try:
        app.patch_swarm_product_approve("patch-swarm-engine-contract", {})
    except app.AgentWorkAppError as exc:
        assert "engine-only run" in str(exc)
    else:
        raise AssertionError("engine run accepted a product approval")


def test_patch_swarm_route_is_served_as_app_shell() -> None:
    assert app.safe_static_path("/patch-swarm").name == "index.html"
    assert app.safe_static_path("/patch-swarm/runs/example").name == "index.html"
