#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import factory_dispatch_core


ROOT = Path(__file__).resolve().parents[1]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def repo_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else ROOT / path


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_step(name: str, command: list[str]) -> dict[str, Any]:
    started = time.perf_counter()
    proc = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return {
        "name": name,
        "command": " ".join(command),
        "exit_code": proc.returncode,
        "passed": proc.returncode == 0,
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        "stdout_tail": proc.stdout[-1200:],
        "stderr_tail": proc.stderr[-1200:],
    }


def lane_for(index: int) -> str:
    lanes = ["coordinator", "builder", "validator", "docs-evidence", "integration"]
    lane = lanes[index % len(lanes)]
    return "builder" if lane == "integration" else lane


def task(index: int, out: Path, task_count: int) -> dict[str, Any]:
    tid = f"factory-runtime-task-{index:02d}"
    deps: list[str] = []
    if index > 5:
        deps.append(f"factory-runtime-task-{index - 5:02d}")
    if index % 11 == 0:
        deps.append("factory-docs-registry")
    owned = [f"{rel(out)}/module/lane-{index % 5}/task-{index:02d}.txt"]
    if index == 8:
        owned = [f"{rel(out)}/module/conflict-a"]
    if index == 9:
        owned = [f"{rel(out)}/module/conflict-a/shared.txt"]
    if index == 18:
        owned = [f"{rel(out)}/module/conflict-b"]
    if index == 19:
        owned = [f"{rel(out)}/module/conflict-b/shared.txt"]
    return {
        "id": tid,
        "title": f"Factory runtime task {index:02d}",
        "lane": lane_for(index),
        "node": "linux",
        "owned_scope": owned,
        "goal": f"Produce dry-run evidence for complex Factory runtime task {index:02d}.",
        "expected_outputs": [{"path": f"{rel(out)}/tasks/{tid}/evidence.md", "description": "Task evidence"}],
        "validation_commands": [f"python3 -m json.tool {rel(out)}/tasks/{tid}/validation.json"],
        "no_model_eligible": True,
        "risk": "medium" if index % 7 == 0 else "low",
        "dependencies": deps,
    }


def create_plan(out: Path, task_count: int) -> dict[str, Any]:
    run_id = out.name
    tasks = [
        {
            "id": "factory-docs-registry",
            "title": "Docs and registry task",
            "lane": "docs-evidence",
            "node": "linux",
            "owned_scope": ["docs/factory-autopilot.md", "docs/factory.md", "data/tools.json", "data/cento-cli.json"],
            "goal": "Keep Factory Autopilot docs and registries aligned with runtime command surface.",
            "expected_outputs": [{"path": f"{rel(out)}/tasks/factory-docs-registry/evidence.md", "description": "Docs registry evidence"}],
            "validation_commands": [f"python3 -m json.tool {rel(out)}/tasks/factory-docs-registry/validation.json"],
            "no_model_eligible": True,
            "risk": "low",
            "dependencies": [],
        }
    ]
    tasks.extend(task(index, out, task_count) for index in range(1, task_count))
    plan = {
        "schema_version": "factory-plan/v1",
        "run_id": run_id,
        "request": {
            "raw": "factory-autopilot-runtime-v1 complex dry-run fixture",
            "normalized_goal": "Exercise a resumable deterministic Factory Autopilot control loop against a complex project.",
        },
        "package": "factory-autopilot-runtime-v1",
        "mode": "dispatch_dry_run",
        "risk": "medium",
        "budget": {
            "ai_call_budget": 0,
            "strong_model_calls_allowed": 0,
            "cheap_worker_calls_allowed": 0,
            "estimated_cost_usd": 0,
            "max_dry_run_budget_usd": 2.0,
        },
        "shared_paths": ["workspace/runs/factory/", "docs/factory.md", "data/tools.json", "data/cento-cli.json"],
        "tasks": tasks,
        "integration": {
            "strategy": "dry_run_control_loop",
            "merge_order": [str(item["id"]) for item in tasks],
            "required_docs": ["docs/factory-autopilot.md", "docs/factory.md", "docs/tool-index.md", "docs/platform-support.md"],
        },
        "validation": {
            "minimum_tier": "tier0",
            "requires_screenshots": False,
            "requires_api_smoke": False,
            "requires_human_review": False,
        },
        "evidence": {"run_dir": rel(out), "summary": rel(out / "e2e-summary.md")},
        "created_at": now_iso(),
        "fixture": {
            "intentional_owned_path_conflicts": [
                {"tasks": ["factory-runtime-task-08", "factory-runtime-task-09"], "path": f"{rel(out)}/module/conflict-a/shared.txt"},
                {"tasks": ["factory-runtime-task-18", "factory-runtime-task-19"], "path": f"{rel(out)}/module/conflict-b/shared.txt"},
            ],
            "storage_pressure_input": rel(out / "autopilot" / "storage-pressure-input.json"),
            "cost_budget_input": rel(out / "autopilot" / "cost-budget-input.json"),
        },
    }
    write_json(out / "factory-plan.json", plan)
    write_json(
        out / "intake.json",
        {
            "schema_version": "factory-intake/v1",
            "run_id": run_id,
            "package": plan["package"],
            "request": plan["request"],
            "mode": "dispatch_dry_run",
            "ai_calls_used": 0,
            "estimated_ai_cost_usd": 0,
            "created_at": now_iso(),
        },
    )
    (out / "request.md").write_text("# Factory Autopilot Runtime Fixture\n\nComplex deterministic dry-run fixture.\n", encoding="utf-8")
    return plan


def add_patch(task_dir: Path, changed_file: str, *, status: str = "passed") -> None:
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "changed-files.txt").write_text(changed_file + "\n", encoding="utf-8")
    (task_dir / "patch.diff").write_text(
        "\n".join(
            [
                f"diff --git a/{changed_file} b/{changed_file}",
                "new file mode 100644",
                "index 0000000..e69de29",
                "--- /dev/null",
                f"+++ b/{changed_file}",
                "@@ -0,0 +1 @@",
                "+dry-run fixture evidence",
                "",
            ]
        ),
        encoding="utf-8",
    )
    write_json(task_dir / "validation-result.json", {"schema_version": "factory-validation-result/v1", "status": status, "ai_calls_used": 0, "estimated_ai_cost_usd": 0, "generated_at": now_iso()})


def seed_backlogs(out: Path, plan: dict[str, Any]) -> None:
    for tid, changed in {
        "factory-runtime-task-08": f"{rel(out)}/module/conflict-a/shared.txt",
        "factory-runtime-task-09": f"{rel(out)}/module/conflict-a/shared.txt",
        "factory-runtime-task-18": f"{rel(out)}/module/conflict-b/shared.txt",
        "factory-runtime-task-19": f"{rel(out)}/module/conflict-b/shared.txt",
        "factory-runtime-task-20": f"{rel(out)}/module/lane-0/task-20.txt",
        "factory-runtime-task-21": f"{rel(out)}/module/lane-1/task-21.txt",
    }.items():
        add_patch(out / "tasks" / tid, changed)
    run_step("collect", ["python3", "scripts/factory.py", "collect", rel(out), "--json"])
    queue = factory_dispatch_core.read_json(out / "queue" / "queue.json")
    validating = {"factory-runtime-task-22", "factory-runtime-task-23", "factory-runtime-task-24", "factory-runtime-task-25", "factory-runtime-task-26"}
    integrating = {"factory-runtime-task-20", "factory-runtime-task-21", "factory-runtime-task-08"}
    collecting = {"factory-runtime-task-09", "factory-runtime-task-18", "factory-runtime-task-19"}
    for item in factory_dispatch_core.normalize_queue_tasks(queue):
        tid = factory_dispatch_core.task_id(item)
        if tid in validating:
            item["status"] = "validating"
            item["last_event"] = "fixture_validation_backlog"
        elif tid in integrating:
            item["status"] = "ready_to_integrate"
            item["last_event"] = "fixture_integration_backlog"
        elif tid in collecting:
            item["status"] = "collecting"
            item["last_event"] = "fixture_patch_backlog"
    factory_dispatch_core.save_queue(out, queue)
    write_json(out / "integration" / "integration-backlog.json", {"schema_version": "factory-integration-backlog/v1", "tasks": sorted(integrating), "generated_at": now_iso()})
    write_json(out / "autopilot" / "storage-pressure-input.json", {"schema_version": "cento-storage-pressure/v1", "storage_pressure": "medium", "fanout_gate": {"should_hold_fanout": True, "should_pause_dispatch": False}, "note": "Fixture input; runtime also reads cento storage pressure --json."})
    write_json(out / "autopilot" / "cost-budget-input.json", {"schema_version": "factory-cost-budget/v1", "max_budget_usd": 2.0, "ai_calls_allowed": 0})
    write_json(
        out / "autopilot" / "factory-state.json",
        {
            "schema_version": "factory-autopilot-runtime-state/v1",
            "run_id": out.name,
            "run_dir": rel(out),
            "phase": "fixture_seeded",
            "cycles_completed": 0,
            "last_action": "",
            "last_progress": False,
            "no_progress_cycles": 0,
            "simulated": {
                "patch_backlog": 2,
                "validation_backlog": 3,
                "integration_backlog": 2,
                "validated_integrated_progress": 0,
                "blocked_reasons": [],
            },
            "artifacts": {},
            "ai_calls_used": 0,
            "estimated_cost_usd": 0,
            "updated_at": now_iso(),
        },
    )


def validate_fixture(out: Path, task_count: int) -> list[str]:
    errors: list[str] = []
    required = [out / "factory-plan.json", out / "queue" / "queue.json", out / "integration", out / "autopilot" / "storage-pressure-input.json"]
    errors.extend(f"missing {rel(path)}" for path in required if not path.exists())
    queue = factory_dispatch_core.read_json(out / "queue" / "queue.json")
    if len(factory_dispatch_core.normalize_queue_tasks(queue)) < task_count:
        errors.append("queue task count below requested task count")
    counts = factory_dispatch_core.queue_stats(factory_dispatch_core.normalize_queue_tasks(queue))
    if counts.get("validating", 0) < 5:
        errors.append("validation backlog was not seeded")
    if counts.get("ready_to_integrate", 0) < 3:
        errors.append("integration backlog was not seeded")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build complex Factory Autopilot runtime dry-run fixture.")
    parser.add_argument("--fixture", default="complex-project")
    parser.add_argument("--tasks", type=int, default=50)
    parser.add_argument("--out", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.fixture != "complex-project":
        raise SystemExit(f"unknown fixture: {args.fixture}")
    out = repo_path(args.out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    task_count = max(50, args.tasks)
    plan = create_plan(out, task_count)
    checks = [
        run_step("validate-plan", ["python3", "scripts/factory_plan.py", "validate", rel(out / "factory-plan.json")]),
        run_step("materialize", ["python3", "scripts/factory.py", "materialize", rel(out)]),
        run_step("queue", ["python3", "scripts/factory.py", "queue", rel(out)]),
    ]
    if all(item["passed"] for item in checks):
        seed_backlogs(out, plan)
    fixture_errors = validate_fixture(out, task_count)
    checks.append({"name": "fixture-shape", "command": "internal fixture validation", "exit_code": 0 if not fixture_errors else 1, "passed": not fixture_errors, "duration_ms": 0, "stdout_tail": "", "stderr_tail": "; ".join(fixture_errors)})
    decision = "approve" if all(item["passed"] for item in checks) else "blocked"
    summary = {
        "schema_version": "factory-autopilot-runtime-e2e-summary/v1",
        "fixture": args.fixture,
        "run_dir": rel(out),
        "decision": decision,
        "task_count": task_count,
        "package": "factory-autopilot-runtime-v1",
        "checks": checks,
        "ai_calls_used": 0,
        "estimated_cost_usd": 0,
        "generated_at": now_iso(),
    }
    write_json(out / "e2e-summary.json", summary)
    (out / "e2e-summary.md").write_text(
        "\n".join(
            [
                "# Factory Autopilot Runtime E2E",
                "",
                f"- Fixture: `{args.fixture}`",
                f"- Decision: `{decision}`",
                f"- Tasks: `{task_count}`",
                "- AI calls used: 0",
                "- Estimated cost USD: 0",
                "",
                "## Checks",
                "",
                *[f"- {'PASS' if item['passed'] else 'FAIL'} `{item['name']}`" for item in checks],
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True) if args.json else f"summary: {rel(out / 'e2e-summary.md')}")
    return 0 if decision == "approve" else 1


if __name__ == "__main__":
    raise SystemExit(main())
