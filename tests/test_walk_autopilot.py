#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import spend_ledger
import parallel_delivery
import walk_autopilot as walk


def factory_scale_args(**overrides):
    values = {
        "proreq_executions": 30,
        "patch_swarm": False,
        "duration_hours": 6.0,
        "min_proreq_calls": 100,
        "execute_proreq": False,
        "proreq_command_timeout": 1,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def configure_factory_scale(monkeypatch, tmp_path: Path) -> Path:
    run_root = tmp_path / "walk-autopilot"
    monkeypatch.setattr(walk, "RUN_ROOT", run_root)
    monkeypatch.setattr(walk, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(walk, "FACTORY_SCALE_LOG_PATH", tmp_path / "logs" / "factory-scale-final-test.log")
    return run_root


def write_fake_factory_scale_patch_swarm(run_dir: Path, tmp_path: Path, milestone_id: str = "milestone-01") -> Path:
    parallel_run = tmp_path / "parallel-delivery" / f"{run_dir.name}-{milestone_id}"
    parallel_run.mkdir(parents=True, exist_ok=True)
    patch_a = parallel_run / "candidate-a.diff"
    patch_b = parallel_run / "candidate-b.diff"
    patch_a.write_text(
        "\n".join(
            [
                "diff --git a/workspace/factory-scale-promotion-test-a.txt b/workspace/factory-scale-promotion-test-a.txt",
                "new file mode 100644",
                "index 0000000..d670460",
                "--- /dev/null",
                "+++ b/workspace/factory-scale-promotion-test-a.txt",
                "@@ -0,0 +1 @@",
                "+candidate-a",
                "",
            ]
        ),
        encoding="utf-8",
    )
    patch_b.write_text(
        "\n".join(
            [
                "diff --git a/workspace/factory-scale-promotion-test-b.txt b/workspace/factory-scale-promotion-test-b.txt",
                "new file mode 100644",
                "index 0000000..15f3b44",
                "--- /dev/null",
                "+++ b/workspace/factory-scale-promotion-test-b.txt",
                "@@ -0,0 +1 @@",
                "+candidate-b",
                "",
            ]
        ),
        encoding="utf-8",
    )
    walk.write_json(parallel_run / "candidate-a.json", {"id": "candidate-a", "status": "validated"})
    walk.write_json(parallel_run / "candidate-b.json", {"id": "candidate-b", "status": "validated"})
    walk.write_json(parallel_run / "candidate-a-validation.json", {"status": "passed"})
    walk.write_json(parallel_run / "candidate-b-validation.json", {"status": "passed"})
    candidates = [
        {
            "id": "candidate-a",
            "execution_id": "lane-a",
            "task_id": "lane-a",
            "provider": "codex-exec",
            "status": "validated",
            "score": 100.0,
            "cost_usd_estimate": 0.0,
            "duration_ms_estimate": 400,
            "touched_paths": ["workspace/factory-scale-promotion-test-a.txt"],
            "patch": {"patch_file": str(patch_a), "sha256": walk.file_fingerprint(patch_a)["sha256"]},
            "candidate_receipt": str(parallel_run / "candidate-a.json"),
            "validation_receipt": str(parallel_run / "candidate-a-validation.json"),
            "errors": [],
        },
        {
            "id": "candidate-b",
            "execution_id": "lane-b",
            "task_id": "lane-b",
            "provider": "api-openai",
            "status": "validated",
            "score": 95.0,
            "cost_usd_estimate": 0.02,
            "duration_ms_estimate": 700,
            "touched_paths": ["workspace/factory-scale-promotion-test-b.txt"],
            "patch": {"patch_file": str(patch_b), "sha256": walk.file_fingerprint(patch_b)["sha256"]},
            "candidate_receipt": str(parallel_run / "candidate-b.json"),
            "validation_receipt": str(parallel_run / "candidate-b-validation.json"),
            "errors": [],
        },
    ]
    walk.write_json(parallel_run / "candidate_index.json", {"schema_version": "cento.patch_swarm.candidate_index.v1", "candidates": candidates})
    walk.write_json(parallel_run / "ranking.json", {"schema_version": "cento.patch_swarm.ranking.v1", "top_candidates": candidates})
    handoff = {
        "schema_version": "cento.patch_swarm.safe_integrator_handoff.v1",
        "status": "ready",
        "selected_candidates": [
            {
                "candidate_id": "candidate-a",
                "execution_id": "lane-a",
                "provider": "codex-exec",
                "patch_file": str(patch_a),
                "touched_paths": ["workspace/factory-scale-promotion-test-a.txt"],
                "score": 100.0,
            }
        ],
    }
    walk.write_json(parallel_run / "safe_integrator_handoff.json", handoff)
    walk.write_json(
        run_dir / "patch-swarm" / milestone_id / "summary.json",
        {
            "schema_version": "cento.factory_scale.patch_swarm_milestone_summary.v1",
            "run_id": run_dir.name,
            "milestone_id": milestone_id,
            "status": "completed",
            "parallel_delivery_run": str(parallel_run),
            "candidate_count": 2,
            "selected_count": 1,
            "estimated_cost_usd": 0.02,
            "safe_integrator_handoff": str(parallel_run / "safe_integrator_handoff.json"),
        },
    )
    walk.factory_scale_append_event(
        run_dir,
        "patch_swarm_completed",
        {
            "milestone_id": milestone_id,
            "status": "completed",
            "candidate_count": 2,
            "selected_count": 1,
            "parallel_delivery_run": str(parallel_run),
            "safe_integrator_handoff": str(parallel_run / "safe_integrator_handoff.json"),
        },
    )
    return parallel_run


def mark_factory_scale_executions_complete(run_dir: Path) -> None:
    manifest = walk.read_json(run_dir / "execution-manifest.json")
    for execution in walk.as_list(manifest.get("executions")):
        if isinstance(execution, dict):
            pipeline_root = walk.factory_scale_seed_proreq_root(run_dir, execution)
            walk.factory_scale_record_proreq_call(
                run_dir,
                execution,
                command_index=10,
                command_name="evidence",
                command=["./scripts/cento.sh", "proreq-light", "evidence"],
                pipeline_root=pipeline_root,
                result={"status": "logged", "exit_code": 0},
            )


def test_spend_ledger_dedupes_openai_response_ids(tmp_path: Path) -> None:
    ledger = tmp_path / "spend-ledger.jsonl"
    first = spend_ledger.build_api_record(
        run_id="run-1",
        lane="pro",
        category="pro",
        model="gpt-5.4-pro",
        status="completed",
        response_id="resp_123",
        usage={"input_tokens": 1000, "output_tokens": 1000},
    )
    second = spend_ledger.build_api_record(
        run_id="run-1",
        lane="pro",
        category="pro",
        model="gpt-5.4-pro",
        status="completed",
        response_id="resp_123",
        usage={"input_tokens": 1000, "output_tokens": 1000},
    )

    spend_ledger.append_record(ledger, first)
    spend_ledger.append_record(ledger, second)
    records = spend_ledger.read_jsonl(ledger)
    summary = spend_ledger.summarize_records(records)

    assert len(records) == 2
    assert records[1]["duplicate_of"] == records[0]["record_id"]
    assert records[1]["cost_usd"] == 0.0
    assert summary["duplicate_count"] == 1
    assert summary["total_cost_usd"] == first["cost_usd"]
    assert summary["factory_cost_usd"] == 0.0
    assert summary["api_cost_usd"] == first["cost_usd"]


def test_spend_ledger_dashboard_total_baseline_is_deduped(tmp_path: Path) -> None:
    ledger = tmp_path / "spend-ledger.jsonl"
    first = spend_ledger.build_dashboard_total_record(run_id="run-1", total_usd=48.21, note="snapshot")
    second = spend_ledger.build_dashboard_total_record(run_id="run-1", total_usd=48.21, note="snapshot")

    spend_ledger.append_record(ledger, first)
    spend_ledger.append_record(ledger, second)
    summary = spend_ledger.summarize_paths([ledger])

    assert summary["dashboard_total_baseline_usd"] == 48.21
    assert summary["total_cost_usd"] == 48.21
    assert summary["duplicate_count"] == 1


def test_live_api_budget_gate_requires_dashboard_total(monkeypatch) -> None:
    monkeypatch.delenv(walk.DASHBOARD_TOTAL_ENV, raising=False)
    args = type("Args", (), {"allow_live_api": True, "hard_cap_usd": 20.0, "dashboard_total_spend_usd": None})()

    gate = walk.live_api_budget_gate(args, {})

    assert gate["allowed"] is False
    assert "--dashboard-total-spend-usd" in gate["reason"]


def test_live_api_budget_gate_blocks_when_dashboard_total_exceeds_cap() -> None:
    args = type("Args", (), {"allow_live_api": True, "hard_cap_usd": 20.0, "dashboard_total_spend_usd": 45.82})()

    gate = walk.live_api_budget_gate(args, {"total_cost_usd": 0.33})

    assert gate["allowed"] is False
    assert gate["dashboard_total_spend_usd"] == 45.82
    assert gate["effective_total_cost_usd"] == 45.82


def test_spend_cap_incident_doc_is_discoverable() -> None:
    root = Path(__file__).resolve().parent.parent
    doc = root / "docs" / "walk-autopilot-spend-cap-incident.md"
    nav = root / "docs" / "nav.html"
    text = doc.read_text(encoding="utf-8")
    nav_text = nav.read_text(encoding="utf-8")

    required = [
        "## What Happened",
        "## Timeline",
        "## Why The Ledger Was Wrong",
        "## New Guardrail",
        "## Verification",
        "$48.21",
        "$0.33742",
        "--dashboard-total-spend-usd",
    ]
    missing = [item for item in required if item not in text]

    assert not missing
    assert "walk-autopilot-spend-cap-incident.md" in nav_text


def test_loop_markdown_contains_required_sections(tmp_path: Path) -> None:
    path = tmp_path / "loops" / "loop-0001.md"

    walk.write_loop_markdown(
        path,
        run_dir=tmp_path,
        loop_number=1,
        findings=["factory dry-run completed"],
        breakthroughs=["ledger dedupe is active"],
        copied_notes="- carried forward",
        next_steps=["run validation"],
        spend={"total_cost_usd": 0.0},
        validation=[{"name": "tools-json", "exit_code": 0}],
        changed_files=[" M scripts/walk_autopilot.py"],
        blockers=[],
        recommended_next_loop="continue",
    )
    text = path.read_text(encoding="utf-8")

    for section in walk.REQUIRED_LOOP_SECTIONS:
        assert f"## {section}" in text
    assert "factory dry-run completed" in text
    assert "ledger dedupe is active" in text


def test_agent_pool_live_failure_classifies_missing_manifest(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(walk, "ROOT", tmp_path)
    payload = {"launched": [{"issue": 100, "lane": "builder", "subject": "Route prompt"}]}
    live_result = {
        "stdout_tail": "Dispatch preflight blocked: canonical story manifest is missing",
        "stderr_tail": "",
        "timed_out": False,
    }

    gaps = walk.manifest_gaps_for_agent_pool_payload(payload, [100])

    assert gaps == [
        {
            "issue": 100,
            "lane": "builder",
            "subject": "Route prompt",
            "story_manifest": "workspace/runs/agent-work/100/story.json",
            "validation_manifest": "workspace/runs/agent-work/100/validation.json",
            "story_missing": True,
            "validation_missing": True,
        }
    ]
    assert walk.classify_agent_pool_live_failure(live_result, payload, gaps) == "missing_canonical_manifest"


def test_live_worker_blockers_treats_successful_retry_as_recovered() -> None:
    commands = [
        {"name": "agent-pool-live-launch", "exit_code": 1},
        {"name": "agent-pool-incident-repair-manifests", "exit_code": 0},
        {"name": "agent-pool-live-retry-after-incident", "exit_code": 0},
    ]

    assert walk.live_worker_blockers(commands) == []


def test_write_agent_pool_incident_bundle(tmp_path: Path) -> None:
    incident_dir = tmp_path / "incidents" / "loop-0001-missing-canonical"
    payload = {
        "incident_dir": str(incident_dir),
        "incident_class": "missing_canonical_manifest",
        "status": "recovered",
        "loop": 1,
        "opened_at": "2026-05-05T00:00:00Z",
        "summary": "handled",
        "issue_ids": [100],
        "manifest_gaps": [{"issue": 100, "lane": "builder", "story_missing": True, "validation_missing": True}],
        "attempts": [{"name": "agent-pool-live-launch", "exit_code": 1}, {"name": "agent-pool-live-retry-after-incident", "exit_code": 0}],
        "resolution": "retry succeeded",
    }

    walk.write_agent_pool_incident(tmp_path, payload)

    assert (incident_dir / "incident.json").exists()
    assert (incident_dir / "attempts.jsonl").read_text(encoding="utf-8").count("\n") == 2
    assert "missing_canonical_manifest" in (incident_dir / "notes.md").read_text(encoding="utf-8")


def test_factory_scale_cron_install_uninstall_is_idempotent(monkeypatch, tmp_path: Path) -> None:
    configure_factory_scale(monkeypatch, tmp_path)
    crontab = tmp_path / "crontab.txt"

    first = walk.factory_scale_install_cron_for_run("factory-scale-test", duration_hours=6, crontab_file=str(crontab))
    second = walk.factory_scale_install_cron_for_run("factory-scale-test", duration_hours=6, crontab_file=str(crontab))
    text = crontab.read_text(encoding="utf-8")

    assert first["status"] == "installed"
    assert second["status"] == "installed"
    assert text.count(walk.FACTORY_SCALE_CRON_BEGIN) == 1
    assert text.count(walk.FACTORY_SCALE_CRON_END) == 1
    assert "*/12 * * * *" in text
    assert "flock -n" in text
    assert "--run-id factory-scale-test" in text

    args = argparse.Namespace(crontab_file=str(crontab), dry_run=False, json=True)
    assert walk.command_factory_scale_uninstall_cron(args) == 0
    assert walk.FACTORY_SCALE_CRON_BEGIN not in crontab.read_text(encoding="utf-8")


def test_factory_scale_tick_selects_one_pending_execution(monkeypatch, tmp_path: Path) -> None:
    run_root = configure_factory_scale(monkeypatch, tmp_path)
    run_dir = run_root / "factory-scale-test"
    walk.factory_scale_init_run(run_dir, factory_scale_args(proreq_executions=3, min_proreq_calls=10))

    args = argparse.Namespace(run_id="factory-scale-test", cron_lock_conflict=False, json=True)
    assert walk.command_factory_scale_tick(args) == 0

    calls = spend_ledger.read_jsonl(run_dir / "proreq-light-calls.jsonl")
    status = walk.factory_scale_status_payload("factory-scale-test")
    assert len(calls) == 10
    assert {item["execution_id"] for item in calls} == {"exec-001"}
    assert status["completed_proreq_executions"] == 1
    assert status["next_execution_id"] == "exec-002"


def test_factory_scale_ledgers_only_append_between_ticks(monkeypatch, tmp_path: Path) -> None:
    run_root = configure_factory_scale(monkeypatch, tmp_path)
    run_dir = run_root / "factory-scale-test"
    walk.factory_scale_init_run(run_dir, factory_scale_args(proreq_executions=2, min_proreq_calls=10))
    args = argparse.Namespace(run_id="factory-scale-test", cron_lock_conflict=False, json=True)

    assert walk.command_factory_scale_tick(args) == 0
    first = (run_dir / "proreq-light-calls.jsonl").read_text(encoding="utf-8")
    assert walk.command_factory_scale_tick(args) == 0
    second = (run_dir / "proreq-light-calls.jsonl").read_text(encoding="utf-8")

    assert second.startswith(first)
    assert len(spend_ledger.read_jsonl(run_dir / "proreq-light-calls.jsonl")) == 20


def test_factory_scale_call_ledger_reaches_minimum_after_ten_executions(monkeypatch, tmp_path: Path) -> None:
    run_root = configure_factory_scale(monkeypatch, tmp_path)
    run_dir = run_root / "factory-scale-test"
    walk.factory_scale_init_run(run_dir, factory_scale_args(proreq_executions=10, min_proreq_calls=100))
    args = argparse.Namespace(run_id="factory-scale-test", cron_lock_conflict=False, json=True)

    for _ in range(10):
        assert walk.command_factory_scale_tick(args) == 0

    status = walk.factory_scale_status_payload("factory-scale-test")
    assert status["proreq_call_count"] == 100
    assert status["min_proreq_calls_met"] is True


def test_factory_scale_manifest_derives_ten_patch_swarm_groups() -> None:
    manifest = walk.factory_scale_manifest(30, patch_swarm=True)
    milestones = manifest["milestones"]

    assert manifest["proreq_execution_count"] == 30
    assert manifest["expected_proreq_call_count"] == 300
    assert manifest["patch_swarm_milestone_count"] == 10
    assert manifest["expected_candidate_receipts"] == 1000
    assert len(milestones) == 10
    assert all(len(item["proreq_execution_ids"]) == 3 for item in milestones)


def test_factory_scale_day_call_target_math() -> None:
    assert walk.factory_scale_executions_for_call_target(3000) == 300
    assert walk.factory_scale_call_target_for_executions(300) == 3000
    assert walk.factory_scale_executions_for_call_target(10000) == 1000


def test_factory_scale_start_day_derives_large_manifest(monkeypatch, tmp_path: Path) -> None:
    run_root = configure_factory_scale(monkeypatch, tmp_path)
    args = argparse.Namespace(
        run_id="factory-scale-day-test",
        target_proreq_calls=3000,
        max_proreq_calls=10000,
        duration_hours=12.0,
        tick_minutes=10,
        batch_size=5,
        patch_swarm_candidate_target=100,
        patch_swarm_max_parallel_agents=5,
        no_patch_swarm=False,
        proreq_command_timeout=1,
        crontab_file=str(tmp_path / "crontab.txt"),
        no_install_cron=True,
        dry_run=False,
        json=True,
    )

    assert walk.command_factory_scale_start_day(args) == 0

    config = walk.read_json(run_root / "factory-scale-day-test" / "config.json")
    status = walk.factory_scale_status_payload("factory-scale-day-test", str(tmp_path / "crontab.txt"))
    assert config["run_mode"] == "day-scale"
    assert config["batch_size"] == 5
    assert config["target_proreq_calls"] == 3000
    assert config["max_proreq_calls"] == 10000
    assert status["proreq_execution_count"] == 300
    assert status["expected_proreq_call_count"] == 3000
    assert status["expected_patch_swarm_runs"] == 100
    assert status["expected_candidate_patch_receipts"] == 10000


def test_factory_scale_start_day_blocks_rounded_calls_above_max(monkeypatch, tmp_path: Path) -> None:
    configure_factory_scale(monkeypatch, tmp_path)
    args = argparse.Namespace(
        run_id="factory-scale-day-test",
        target_proreq_calls=31,
        max_proreq_calls=31,
        duration_hours=12.0,
        tick_minutes=10,
        batch_size=5,
        patch_swarm_candidate_target=100,
        patch_swarm_max_parallel_agents=5,
        no_patch_swarm=False,
        proreq_command_timeout=1,
        crontab_file=str(tmp_path / "crontab.txt"),
        no_install_cron=True,
        dry_run=False,
        json=True,
    )

    assert walk.command_factory_scale_start_day(args) == 2


def test_factory_scale_tick_batch_runs_multiple_executions(monkeypatch, tmp_path: Path) -> None:
    run_root = configure_factory_scale(monkeypatch, tmp_path)
    run_dir = run_root / "factory-scale-test"
    walk.factory_scale_init_run(run_dir, factory_scale_args(proreq_executions=5, min_proreq_calls=50))
    args = argparse.Namespace(run_id="factory-scale-test", batch_size=3, cron_lock_conflict=False, json=True)

    assert walk.command_factory_scale_tick(args) == 0

    status = walk.factory_scale_status_payload("factory-scale-test")
    assert status["completed_proreq_executions"] == 3
    assert status["proreq_call_count"] == 30
    assert status["next_execution_id"] == "exec-004"


def test_factory_scale_day_cron_uses_batch_schedule(monkeypatch, tmp_path: Path) -> None:
    configure_factory_scale(monkeypatch, tmp_path)
    crontab = tmp_path / "crontab.txt"
    args = argparse.Namespace(
        run_id="factory-scale-day-test",
        target_proreq_calls=100,
        max_proreq_calls=1000,
        duration_hours=12.0,
        tick_minutes=10,
        batch_size=5,
        patch_swarm_candidate_target=100,
        patch_swarm_max_parallel_agents=5,
        no_patch_swarm=False,
        proreq_command_timeout=1,
        crontab_file=str(crontab),
        no_install_cron=False,
        dry_run=False,
        json=True,
    )

    assert walk.command_factory_scale_start_day(args) == 0

    text = crontab.read_text(encoding="utf-8")
    assert "*/10 * * * *" in text
    assert "--batch-size 5" in text
    assert "factory-scale-day.lock" in text


def test_latest_factory_scale_run_uses_mtime_not_lexical_order(monkeypatch, tmp_path: Path) -> None:
    run_root = configure_factory_scale(monkeypatch, tmp_path)
    older = run_root / "factory-scale-z-older"
    newer = run_root / "factory-scale-a-newer"
    older.mkdir(parents=True)
    newer.mkdir(parents=True)
    os.utime(older, (1000, 1000))
    os.utime(newer, (2000, 2000))

    assert walk.latest_factory_scale_run_dir() == newer


def test_factory_scale_status_is_derived_from_call_logs(monkeypatch, tmp_path: Path) -> None:
    run_root = configure_factory_scale(monkeypatch, tmp_path)
    run_dir = run_root / "factory-scale-test"
    walk.factory_scale_init_run(run_dir, factory_scale_args(proreq_executions=3, min_proreq_calls=10))
    execution = walk.factory_scale_next_execution(run_dir)
    assert execution is not None
    pipeline_root = walk.factory_scale_seed_proreq_root(run_dir, execution)

    walk.factory_scale_record_proreq_call(
        run_dir,
        execution,
        command_index=10,
        command_name="evidence",
        command=["./scripts/cento.sh", "proreq-light", "evidence"],
        pipeline_root=pipeline_root,
        result={"status": "logged", "exit_code": 0},
    )

    status = walk.factory_scale_status_payload("factory-scale-test")
    assert status["completed_proreq_executions"] == 1
    assert status["proreq_call_count"] == 1
    assert status["next_execution_id"] == "exec-002"


def test_factory_scale_completed_tick_does_not_spam_run_complete(monkeypatch, tmp_path: Path) -> None:
    run_root = configure_factory_scale(monkeypatch, tmp_path)
    run_dir = run_root / "factory-scale-test"
    walk.factory_scale_init_run(run_dir, factory_scale_args(proreq_executions=1, min_proreq_calls=1))
    args = argparse.Namespace(run_id="factory-scale-test", cron_lock_conflict=False, json=True)

    assert walk.command_factory_scale_tick(args) == 0
    assert walk.command_factory_scale_tick(args) == 0
    events_after_complete = (run_dir / "events.jsonl").read_text(encoding="utf-8")
    metrics_after_complete = (run_dir / "metrics.jsonl").read_text(encoding="utf-8")
    assert walk.command_factory_scale_tick(args) == 0

    assert (run_dir / "events.jsonl").read_text(encoding="utf-8") == events_after_complete
    assert (run_dir / "metrics.jsonl").read_text(encoding="utf-8") == metrics_after_complete


def test_factory_scale_no_overlap_preflight_detects_active_process(monkeypatch, tmp_path: Path) -> None:
    configure_factory_scale(monkeypatch, tmp_path)

    payload = walk.factory_scale_no_overlap_preflight(
        "factory-scale-new",
        process_lines=["123 00:12 python3 scripts/walk_autopilot.py factory-scale tick --run-id factory-scale-active --json"],
    )

    assert payload["active"] is True
    assert payload["decision"] == "attach_existing"
    assert payload["active_processes"][0]["pid"] == 123


def test_factory_scale_live_api_rate_limit_blocks_tight_loop() -> None:
    record = spend_ledger.build_api_record(
        run_id="factory-scale-test",
        lane="pro",
        category="pro",
        model="gpt-5.4-pro",
        status="completed",
        response_id="resp_recent",
        usage={"input_tokens": 1, "output_tokens": 1},
    )
    record["written_at"] = "2026-05-06T00:55:00Z"

    payload = walk.factory_scale_live_api_rate_limit(
        [record],
        max_calls_per_hour=4,
        min_spacing_seconds=900,
        checked_at=datetime(2026, 5, 6, 1, 0, tzinfo=timezone.utc),
    )

    assert payload["allowed"] is False
    assert payload["recent_live_call_count"] == 1
    assert "minimum spacing" in payload["blocked_reasons"][0]


def test_factory_scale_candidate_matrix_derives_handoffs(monkeypatch, tmp_path: Path) -> None:
    run_root = configure_factory_scale(monkeypatch, tmp_path)
    run_dir = run_root / "factory-scale-test"
    walk.factory_scale_init_run(run_dir, factory_scale_args(proreq_executions=3, min_proreq_calls=3, patch_swarm=True))
    mark_factory_scale_executions_complete(run_dir)
    write_fake_factory_scale_patch_swarm(run_dir, tmp_path)

    matrix = walk.factory_scale_candidate_matrix(run_dir, promotion_limit=1)

    assert matrix["candidate_count"] == 2
    assert matrix["selected_count"] == 1
    assert matrix["promotion_candidate_count"] == 1
    assert matrix["provider_counts"] == {"api-openai": 1, "codex-exec": 1}
    assert matrix["selected_candidates"][0]["candidate_id"] == "candidate-a"


def test_factory_scale_candidate_matrix_handles_partial_milestone_without_summary(monkeypatch, tmp_path: Path) -> None:
    run_root = configure_factory_scale(monkeypatch, tmp_path)
    run_dir = run_root / "factory-scale-test"
    walk.factory_scale_init_run(run_dir, factory_scale_args(proreq_executions=4, min_proreq_calls=4, patch_swarm=True))
    mark_factory_scale_executions_complete(run_dir)
    write_fake_factory_scale_patch_swarm(run_dir, tmp_path, milestone_id="milestone-01")

    matrix = walk.factory_scale_candidate_matrix(run_dir, promotion_limit=10)

    assert matrix["candidate_count"] == 2
    assert matrix["selected_count"] == 1
    assert any(str(path).endswith("factory-scale-test/patch-swarm/milestone-02/summary.json") for path in matrix["validation_taxonomy"]["missing_artifacts"])


def test_factory_scale_advance_writes_guard_matrix_and_report(monkeypatch, tmp_path: Path) -> None:
    run_root = configure_factory_scale(monkeypatch, tmp_path)
    run_dir = run_root / "factory-scale-test"
    walk.factory_scale_init_run(run_dir, factory_scale_args(proreq_executions=3, min_proreq_calls=3, patch_swarm=True))
    mark_factory_scale_executions_complete(run_dir)
    write_fake_factory_scale_patch_swarm(run_dir, tmp_path)
    args = argparse.Namespace(
        run_id="factory-scale-test",
        crontab_file=str(tmp_path / "crontab.txt"),
        promotion_limit=1,
        allow_incomplete=False,
        allow_live_api=False,
        dashboard_total_spend_usd=None,
        hard_cap_usd=25.0,
        max_live_calls_per_hour=4,
        min_live_call_spacing_seconds=900,
        json=True,
    )

    assert walk.command_factory_scale_advance(args) == 0
    matrix = walk.read_json(run_dir / "advance" / "candidate-matrix.json")
    guard = walk.read_json(run_dir / "advance" / "live-api-guard.json")
    promotion = walk.read_json(run_dir / "advance" / "safe-integrator-promotion-plan.json")

    assert matrix["candidate_count"] == 2
    assert guard["live_api_enabled"] is False
    assert promotion["promotion_plan_count"] == 1
    assert (run_dir / "advance" / "morning-report.md").exists()


def test_factory_scale_promote_normalizes_advance_plan_into_factory_candidates(monkeypatch, tmp_path: Path) -> None:
    run_root = configure_factory_scale(monkeypatch, tmp_path)
    run_dir = run_root / "factory-scale-test"
    walk.factory_scale_init_run(run_dir, factory_scale_args(proreq_executions=3, min_proreq_calls=3, patch_swarm=True))
    mark_factory_scale_executions_complete(run_dir)
    write_fake_factory_scale_patch_swarm(run_dir, tmp_path)
    advance_args = argparse.Namespace(
        run_id="factory-scale-test",
        crontab_file=str(tmp_path / "crontab.txt"),
        promotion_limit=1,
        allow_incomplete=False,
        allow_live_api=False,
        dashboard_total_spend_usd=None,
        hard_cap_usd=25.0,
        max_live_calls_per_hour=4,
        min_live_call_spacing_seconds=900,
        json=True,
    )
    assert walk.command_factory_scale_advance(advance_args) == 0
    captured: dict[str, object] = {}

    def fake_promote(source_run_dir: Path, selected: list[dict[str, object]], **kwargs: object) -> dict[str, object]:
        captured["source_run_dir"] = source_run_dir
        captured["selected"] = selected
        captured["kwargs"] = kwargs
        return {
            "schema_version": "cento.patch_swarm.factory_promotion.v1",
            "status": "ready_for_apply",
            "factory_run_dir": "workspace/runs/factory/factory-scale-test-promotion",
            "candidate_count": len(selected),
            "fanout_status": "passed",
        }

    monkeypatch.setattr(parallel_delivery, "promote_patch_swarm_to_factory", fake_promote)
    promote_args = argparse.Namespace(
        run_id="factory-scale-test",
        crontab_file=str(tmp_path / "crontab.txt"),
        promotion_plan="",
        factory_run="workspace/runs/factory/factory-scale-test-promotion",
        limit=1,
        exclusive_paths=True,
        apply=False,
        validate_each=False,
        branch="",
        worktree="",
        allow_incomplete=False,
        json=True,
    )

    assert walk.command_factory_scale_promote(promote_args) == 0

    selected = captured["selected"]
    assert isinstance(selected, list)
    assert selected[0]["schema_version"] == parallel_delivery.SCHEMA_PATCH_SWARM_CANDIDATE
    assert selected[0]["execution_id"] == "milestone-01-lane-a-0001"
    assert selected[0]["patch"]["sha256"]
    payload = walk.read_json(run_dir / "advance" / "factory-promotion-factory-scale-test-promotion.json")
    assert payload["selected_count"] == 1
    assert payload["factory_promotion"]["fanout_status"] == "passed"


def test_proreq_light_pipeline_root_env_override_does_not_mutate_active_root(monkeypatch, tmp_path: Path) -> None:
    active_root = tmp_path / "active-dev-pipeline"
    isolated_root = tmp_path / "isolated-proreq-light"
    monkeypatch.setenv("CENTO_DEV_PIPELINE_STUDIO_ROOT", str(isolated_root))
    import dev_pipeline_hard_proreq as hard

    hard = importlib.reload(hard)
    hard.write_json(
        isolated_root / "execution" / "execution_run.json",
        {"run_id": "isolated-run", "prompt": "isolate proreq light root", "issue_subject": "isolate"},
    )

    assert hard.PIPELINE_ROOT == isolated_root
    assert hard.command_intake(argparse.Namespace()) == 0
    assert (isolated_root / "execution" / "hard-proreq" / "isolated-run" / "operator_intake.json").exists()
    assert not active_root.exists()

    monkeypatch.delenv("CENTO_DEV_PIPELINE_STUDIO_ROOT", raising=False)
    importlib.reload(hard)
