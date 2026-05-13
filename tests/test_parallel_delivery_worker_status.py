from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import parallel_delivery_worker_status as worker_status  # noqa: E402


ROOT = Path(__file__).resolve().parent.parent
FIXED_TS = "2026-01-01T00:00:00Z"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_fixture(tmp_path: Path, run_id: str = "worker-status-fixture") -> Path:
    run_dir = tmp_path / run_id
    payload = worker_status.build_worker_status_fixture(
        run_dir,
        run_id=run_id,
        candidate_target=100,
        max_parallel_agents=5,
        timestamp=FIXED_TS,
    )
    assert payload["ok"], payload
    return run_dir


def test_dry_run_worker_pool_plan_creates_100_candidates_with_bounded_batches(tmp_path: Path) -> None:
    run_dir = build_fixture(tmp_path)
    plan = read_json(run_dir / "worker-pool-plan.json")

    assert plan["candidate_count"] == 100
    assert plan["max_parallel_agents"] == 5
    assert plan["dry_run"] is True
    assert plan["launch_external_agents"] is False
    assert len(plan["tasks"]) == 100
    assert len(plan["batches"]) == 20
    assert all(len(batch["task_ids"]) <= 5 for batch in plan["batches"])


def test_no_task_appears_in_multiple_batches(tmp_path: Path) -> None:
    run_dir = build_fixture(tmp_path)
    plan = read_json(run_dir / "worker-pool-plan.json")
    seen: list[str] = []

    for batch in plan["batches"]:
        seen.extend(batch["task_ids"])

    assert len(seen) == 100
    assert len(set(seen)) == 100
    assert set(seen) == {f"task-{index:04d}" for index in range(1, 101)}


def test_status_json_summary_counts_match_fixture_states(tmp_path: Path) -> None:
    run_dir = build_fixture(tmp_path)
    status = read_json(run_dir / "worker-status.json")

    assert status["summary"] == {
        "candidate_tasks": 100,
        "max_parallel_agents": 5,
        "active": 5,
        "pending": 92,
        "completed": 1,
        "blocked": 1,
        "stale": 1,
        "failed": 0,
        "dry_run": True,
    }


def test_queue_ledger_parses_and_contains_required_events(tmp_path: Path) -> None:
    run_dir = build_fixture(tmp_path)
    events = read_jsonl(run_dir / "worker-queue-ledger.jsonl")
    event_types = {event["event_type"] for event in events}

    assert {"queue_created", "task_queued", "dispatch_planned", "dispatch_skipped_dry_run", "status_snapshot"} <= event_types
    assert len([event for event in events if event["event_type"] == "task_queued"]) == 100
    assert all(event["schema_version"] == 1 for event in events)
    assert all(event["artifact_type"] == "worker-queue-event" for event in events)


def test_stale_and_blocked_fixture_tasks_are_detected(tmp_path: Path) -> None:
    run_dir = build_fixture(tmp_path)
    status = read_json(run_dir / "worker-status.json")
    stale = read_json(run_dir / "stale-workers.json")

    stale_tasks = [task for task in status["tasks"] if task["stale"]]
    blocked_tasks = [task for task in status["tasks"] if task["state"] == "blocked"]

    assert [task["task_id"] for task in stale_tasks] == ["task-0008"]
    assert [task["task_id"] for task in blocked_tasks] == ["task-0007"]
    assert stale["stale_workers"][0]["task_id"] == "task-0008"
    assert "manual review" in blocked_tasks[0]["blocked_reason"]


def test_dry_run_dispatch_does_not_execute_external_launch(tmp_path: Path) -> None:
    run_dir = build_fixture(tmp_path)
    dispatch = read_json(run_dir / "dry-run-dispatch.json")

    assert dispatch["dry_run"] is True
    assert dispatch["live_dispatch"] is False
    assert dispatch["external_launches"] == []
    assert dispatch["commands_that_would_run"] == []
    assert "cento agent-pool-kick" in dispatch["commands_not_run"]
    assert "external Codex launch" in dispatch["commands_not_run"]


def test_process_visibility_is_read_only_and_platform_guarded(tmp_path: Path) -> None:
    run_dir = build_fixture(tmp_path)
    process = read_json(run_dir / "process-visibility.json")

    assert process["platform"]["system"] in {"unknown", "linux", "darwin", "windows"}
    assert "process_status_supported" in process["platform"]
    assert process["integrations"]["agent_processes"]["read_only"] is True
    assert process["integrations"]["cluster"]["read_only"] is True
    assert process["integrations"]["bridge"]["read_only"] is True
    assert process["integrations"]["agent_pool_kick"]["launch_not_performed"] is True
    assert all(task["process_id"] is None for task in process["tasks"])


def test_console_status_contains_ui_ready_fields(tmp_path: Path) -> None:
    run_dir = build_fixture(tmp_path)
    console = read_json(run_dir / "console-status.json")

    assert console["artifact_type"] == "parallel-delivery-console-status"
    assert console["run_id"] == "worker-status-fixture"
    assert console["state"] == "dry_run_dispatch_planned"
    assert console["candidate_tasks"] == 100
    assert console["max_parallel_agents"] == 5
    assert console["risk"] == "warning"
    assert console["links"]["worker_status"] == "worker-status.json"
    assert console["next_operator_action"]


def test_status_json_is_stable_parseable_and_validates(tmp_path: Path) -> None:
    run_dir = build_fixture(tmp_path, "stable-worker-status")
    first = (run_dir / "worker-status.json").read_text(encoding="utf-8")
    build_fixture(tmp_path, "stable-worker-status")
    second = (run_dir / "worker-status.json").read_text(encoding="utf-8")
    validation = worker_status.validate_worker_status_run(run_dir)

    assert json.loads(first)["artifact_type"] == "worker-status"
    assert first == second
    assert validation["ok"], validation
    assert validation["summary"]["candidate_tasks"] == 100
    assert validation["summary"]["max_parallel_agents"] == 5


def test_parallel_delivery_cli_dispatch_and_worker_status_json(tmp_path: Path) -> None:
    run_dir = tmp_path / "cli-worker-status"
    dispatch = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "parallel_delivery.py"),
            "patch-swarm",
            "dispatch",
            "--run-dir",
            str(run_dir),
            "--run-id",
            "cli-worker-status",
            "--candidate-target",
            "100",
            "--max-parallel-agents",
            "5",
            "--dry-run",
            "--fixture",
            "--json",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert dispatch.returncode == 0, dispatch.stderr
    dispatch_payload = json.loads(dispatch.stdout)
    assert dispatch_payload["ok"] is True
    assert dispatch_payload["dry_run"] is True
    assert dispatch_payload["live_dispatch"] is False
    assert dispatch_payload["candidate_tasks"] == 100

    status = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "parallel_delivery.py"),
            "patch-swarm",
            "worker-status",
            "--run-dir",
            str(run_dir),
            "--json",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert status.returncode == 0, status.stderr
    status_payload = json.loads(status.stdout)
    assert status_payload["ok"] is True
    assert status_payload["candidate_tasks"] == 100
    assert status_payload["stale"] == 1
