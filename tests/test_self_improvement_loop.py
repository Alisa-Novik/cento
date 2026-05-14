#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import parallel_delivery as pd  # noqa: E402


def test_self_improve_run_prompts_chain_previous_guidance(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(pd, "SELF_IMPROVE_RUNS_ROOT", tmp_path / "nightly")
    continuous = tmp_path / "continuous" / "20260505T000000Z"
    continuous.mkdir(parents=True)
    (continuous / "validation_handoff.json").write_text(
        json.dumps({"next_cycle_request": {"objective": "Improve the loop from the previous handoff."}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(pd, "CONTINUOUS_PROREQ_ROOT", tmp_path / "continuous")

    prompts: list[str] = []

    def fake_start(payload: dict, spawn: bool = False) -> dict:
        prompts.append(payload["inputs"][0]["answer"])
        return {"run_id": f"child-{len(prompts):02d}"}

    monkeypatch.setattr(pd.app, "dev_pipeline_start_pipeline_run", fake_start)
    monkeypatch.setattr(pd.app, "dev_pipeline_spawn_execution_e2e", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(pd, "wait_for_pipeline", lambda run_id, *_args, **_kwargs: {"status": "completed", "run_id": run_id})
    monkeypatch.setattr(pd, "summarize_hard_proreq", lambda run_id: {"story_count": 10, "parallel_patch_workset": f"workspace/{run_id}/workset.json"})
    monkeypatch.setattr(pd, "pro_state_for_run", lambda _root: {"status": "completed", "plan_valid": True, "reason": ""})
    monkeypatch.setattr(pd, "image_state_for_run", lambda _root: {"status": "failed", "http_status": 403, "blocking": False, "reason": "gpt-image-2 forbidden"})
    monkeypatch.setattr(pd, "workset_declared_path_policy", lambda _path: {"runtime": "api-openai", "allow_creates": True})
    monkeypatch.setattr(pd, "run_workset_check", lambda *_args, **_kwargs: {"status": "passed", "exit_code": 0, "stderr": ""})
    monkeypatch.setattr(pd, "workset_task_count", lambda _path: 10)

    args = argparse.Namespace(
        run_dir="",
        sleep_seconds=0.0,
        poll_seconds=0.0,
        per_run_timeout=1,
        step_timeout=1,
        pro_timeout=1,
        image_timeout=1,
        reference_screenshot="",
        live_pro=False,
        plan_only=False,
        scheduler_trigger="test",
        cron_time="02:30",
        quiet=True,
        json=True,
    )

    assert pd.command_self_improve_run(args) == 0
    assert len(prompts) == 4
    assert "No previous pass; establish scope" in prompts[0]
    assert "Use pass 1 Scope And Guardrails guidance" in prompts[1]
    assert "Use pass 2 Architecture guidance" in prompts[2]
    assert "Use pass 3 Integration And Workset Strategy guidance" in prompts[3]

    latest = tmp_path / "nightly" / "latest"
    assert (latest / "next_cycle_request.json").exists()
    assert (latest / "validation_gates.json").exists()


def test_self_improve_missing_pro_artifact_blocks_promotion(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(pd, "SELF_IMPROVE_RUNS_ROOT", tmp_path / "nightly")
    run_dir = tmp_path / "nightly" / "20260505T010000Z"
    run_dir.mkdir(parents=True)
    manifest = {"schema_version": pd.SCHEMA_SELF_MANIFEST, "cycle_id": run_dir.name}
    pd.write_self_json(run_dir, "nightly_cycle_manifest.json", manifest)
    for index in range(1, 5):
        degraded = index == 3
        record = {
            "schema_version": pd.SCHEMA_SELF_PASS,
            "cycle_pass": index,
            "pass_id": f"pass-{index}",
            "status": "degraded" if degraded else "completed",
            "blocking_reasons": ["Pro plan artifacts were missing or blank when summarized."] if degraded else [],
            "pro_state": {"plan_valid": not degraded, "reason": "missing" if degraded else ""},
            "image_state": {"status": "failed", "http_status": 403, "blocking": False},
            "workset_check": {"status": "passed", "stderr": ""},
        }
        pd.write_self_json(run_dir, f"pass_{index:02d}_child_run_summary.json", record)

    gates = pd.self_improve_validation(run_dir)
    recommendation = pd.promotion_recommendation([pd.read_json(run_dir / f"pass_{index:02d}_child_run_summary.json") for index in range(1, 5)], gates)

    assert gates["status"] == "failed"
    assert any(item["name"] == "pass_03.pro_artifacts" and item["status"] == "failed" for item in gates["blocking"])
    assert recommendation["recommendation"] == "repair_pipeline_first"


def test_image_403_is_nonblocking_evidence(tmp_path: Path) -> None:
    run_root = tmp_path / "hard-proreq" / "run-image-403"
    run_root.mkdir(parents=True)
    (run_root / "image_generation_response.json").write_text(
        json.dumps(
            {
                "schema_version": "cento.hard_proreq.image_response.v1",
                "status": "failed",
                "http_status": 403,
                "model": "gpt-image-2",
                "response": {"error": {"message": "organization must be verified"}},
            }
        ),
        encoding="utf-8",
    )

    state = pd.image_state_for_run(run_root)

    assert state["status"] == "failed"
    assert state["http_status"] == 403
    assert state["blocking"] is False
    assert "verified" in state["reason"]


def test_self_improve_cron_install_status_and_uninstall(tmp_path: Path) -> None:
    crontab = tmp_path / "crontab.txt"

    install_args = argparse.Namespace(time="02:30", crontab_file=str(crontab), dry_run=False, json=True)
    assert pd.command_self_improve_install_cron(install_args) == 0
    text = crontab.read_text(encoding="utf-8")
    assert pd.SELF_CRON_BEGIN in text
    assert "30 2 * * *" in text

    status = pd.self_improve_status_payload(None, crontab_file=str(crontab))
    assert status["cron_installed"] is True

    uninstall_args = argparse.Namespace(crontab_file=str(crontab), dry_run=False, json=True)
    assert pd.command_self_improve_uninstall_cron(uninstall_args) == 0
    assert pd.SELF_CRON_BEGIN not in crontab.read_text(encoding="utf-8")


def test_self_improve_parser_exposes_e2e_flags() -> None:
    parser = pd.build_parser()
    args = parser.parse_args(
        [
            "self-improve",
            "e2e",
            "--candidate-target",
            "30",
            "--max-parallel-agents",
            "3",
            "--budget-cap-usd",
            "1",
            "--max-budget-usd",
            "1",
            "--apply",
            "--validate-each",
            "--auto-merge-gate",
            "--json",
        ]
    )

    assert args.func == pd.command_self_improve_e2e
    assert args.candidate_target == 30
    assert args.max_parallel_agents == 3
    assert args.budget_cap_usd == 1
    assert args.max_budget_usd == 1
    assert args.apply is True
    assert args.validate_each is True
    assert args.auto_merge_gate is True


def test_self_improve_e2e_fixture_promotes_to_factory_and_dry_run_merge_gate(monkeypatch, capsys) -> None:
    run_id = "self-improve-e2e-test"
    run_dir = pd.SELF_IMPROVE_E2E_RUNS_ROOT / run_id
    factory_run = pd.FACTORY_RUNS_ROOT / f"ai-self-improvement-e2e-{run_id}"
    worktree = pd.ROOT / "workspace" / "factory-integration-worktrees" / f"{run_id}-pytest"
    args = argparse.Namespace(
        run_id=run_id,
        candidate_target=10,
        max_parallel_agents=2,
        providers="codex-exec,claude-code,api-openai",
        budget_cap_usd=1.0,
        max_budget_usd=1.0,
        api_sandbox_candidates=1,
        api_profile=pd.PATCH_SWARM_API_PROFILE,
        api_config=str(pd.ROOT / ".cento" / "api_workers.yaml"),
        fixture_only=True,
        apply=True,
        validate_each=True,
        auto_merge_gate=True,
        branch=f"factory/{run_id}/integration",
        worktree=str(worktree),
        limit=1,
        json=True,
    )

    assert pd.command_self_improve_e2e(args) == 0
    output = json.loads(capsys.readouterr().out)
    gate = json.loads((run_dir / "auto_merge_gate.json").read_text(encoding="utf-8"))

    assert output["status"] in {"applied", "auto_merge_blocked_by_environment"}
    assert (factory_run / "integration" / "validation-fanout.json").exists()
    assert gate["dry_run"] is True
    assert gate["push_requested"] is False
    assert (pd.self_e2e_latest_dir() / "e2e_manifest.json").exists()


def test_workset_check_missing_paths_require_declared_create_policy() -> None:
    fixture = ROOT / "tests" / "fixtures" / "cento_workset" / "workset.execute.api.json"

    strict = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "cento_workset.py"), "check", str(fixture), "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert strict.returncode == 1
    assert "write path does not exist" in strict.stdout

    api_policy = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "cento_workset.py"), "check", str(fixture), "--runtime", "api-openai", "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert api_policy.returncode == 0, api_policy.stderr
    payload = json.loads(api_policy.stdout)
    assert payload["path_policy"]["allow_creates"] is True
