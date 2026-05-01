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


ROOT = Path(__file__).resolve().parents[1]


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


def git_sha(short: bool = True) -> str:
    command = ["git", "rev-parse", "--short", "HEAD"] if short else ["git", "rev-parse", "HEAD"]
    proc = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
    return proc.stdout.strip()


def run_step(name: str, command: list[str]) -> dict[str, Any]:
    start = time.perf_counter()
    proc = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return {
        "name": name,
        "command": " ".join(command),
        "exit_code": proc.returncode,
        "passed": proc.returncode == 0,
        "duration_ms": round((time.perf_counter() - start) * 1000, 3),
        "stdout_tail": proc.stdout[-1600:],
        "stderr_tail": proc.stderr[-1600:],
    }


def patch_for_new_file(path: str, content: str) -> str:
    lines = content.splitlines()
    body = "\n".join(f"+{line}" for line in lines)
    return (
        f"diff --git a/{path} b/{path}\n"
        "new file mode 100644\n"
        "index 0000000..1111111\n"
        "--- /dev/null\n"
        f"+++ b/{path}\n"
        f"@@ -0,0 +1,{len(lines)} @@\n"
        f"{body}\n"
    )


def task(task_id: str, title: str, path: str, deps: list[str]) -> dict[str, Any]:
    return {
        "id": task_id,
        "title": title,
        "lane": "builder",
        "node": "linux",
        "owned_scope": [path],
        "goal": f"Create integrated fixture artifact {path}.",
        "expected_outputs": [{"path": path, "description": title}],
        "validation_commands": [f"test -f {path}"],
        "no_model_eligible": True,
        "risk": "low",
        "dependencies": deps,
    }


def create_run(out: Path) -> list[dict[str, str]]:
    run_id = out.name
    module_root = f"workspace/runs/factory/{run_id}/module"
    tasks = [
        task("crm-schema-extension", "CRM schema extension", f"{module_root}/crm-schema.json", []),
        task("career-commands", "Career command surface", f"{module_root}/commands.json", ["crm-schema-extension"]),
        task("release-notes", "Release notes", f"{module_root}/release-notes.md", ["career-commands"]),
    ]
    intake = {
        "schema_version": "factory-intake/v1",
        "run_id": run_id,
        "request": {"raw": "integrate the career consulting fixture module", "normalized_goal": "Create a validated Safe Integrator release candidate fixture."},
        "package": "factory-integration-v1",
        "mode": "integration_fixture",
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "ai_calls_used": 0,
        "estimated_ai_cost_usd": 0,
    }
    plan = {
        "schema_version": "factory-plan/v1",
        "run_id": run_id,
        "request": intake["request"],
        "package": "factory-integration-v1",
        "mode": "dispatch_dry_run",
        "risk": "low",
        "budget": {"ai_call_budget": 0, "strong_model_calls_allowed": 0, "cheap_worker_calls_allowed": 0, "estimated_cost_usd": 0},
        "shared_paths": [],
        "tasks": tasks,
        "integration": {
            "strategy": "safe_integrator_fixture",
            "merge_order": [item["id"] for item in tasks],
            "required_docs": ["README.md", "docs/tool-index.md", "docs/platform-support.md", "docs/factory.md"],
        },
        "validation": {"minimum_tier": "tier0", "requires_screenshots": False, "requires_api_smoke": False, "requires_human_review": False},
        "evidence": {"run_dir": rel(out), "summary": rel(out / "summary.md")},
        "created_at": intake["created_at"],
    }
    write_json(out / "intake.json", intake)
    (out / "request.md").write_text("# Factory Integration Fixture\n\nSafe Integrator zero-AI fixture.\n", encoding="utf-8")
    write_json(out / "factory-plan.json", plan)
    return [{"task_id": item["id"], "path": item["owned_scope"][0]} for item in tasks]


def create_patch_bundles(out: Path, patch_specs: list[dict[str, str]]) -> None:
    patches = []
    for spec in patch_specs:
        task_id = spec["task_id"]
        path = spec["path"]
        content = json.dumps({"task": task_id, "ai_calls_used": 0}, indent=2) if path.endswith(".json") else "# Release Notes\n\nSafe Integrator fixture release candidate.\n"
        patch_dir = out / "patches" / task_id
        patch_dir.mkdir(parents=True, exist_ok=True)
        (patch_dir / "patch.diff").write_text(patch_for_new_file(path, content), encoding="utf-8")
        (patch_dir / "changed-files.txt").write_text(path + "\n", encoding="utf-8")
        (patch_dir / "diffstat.txt").write_text(f" {path} | {len(content.splitlines())} +\n", encoding="utf-8")
        (patch_dir / "handoff.md").write_text(f"# {task_id} Handoff\n\nFixture patch ready for Safe Integrator.\n", encoding="utf-8")
        write_json(patch_dir / "validation-result.json", {"schema_version": "factory-validation-result/v1", "status": "passed", "ai_calls_used": 0})
        evidence = patch_dir / "evidence"
        evidence.mkdir(exist_ok=True)
        (evidence / "validation.log").write_text("fixture validation passed\n", encoding="utf-8")
        patch = {
            "schema_version": "factory-patch/v1",
            "run_id": out.name,
            "task_id": task_id,
            "issue_id": None,
            "base_sha": git_sha(),
            "worker_run_id": f"fixture-{task_id}",
            "patch_file": "patch.diff",
            "changed_files": [path],
            "diffstat_file": "diffstat.txt",
            "handoff_file": "handoff.md",
            "validation_result": "validation-result.json",
            "evidence_paths": ["evidence/validation.log"],
            "collection_state": "collected",
            "owned_path_check": "passed",
            "git_apply_check": "pending",
            "docs_registry_gate": "not_applicable",
            "integration_status": "candidate",
        }
        write_json(patch_dir / "patch.json", patch)
        patches.append({"task_id": task_id, "patch_bundle": rel(patch_dir / "patch.json"), "state": "collected", "integration_status": "candidate"})
    write_json(out / "patch-collection-summary.json", {"schema_version": "factory-patch-collection/v1", "run_id": out.name, "patches": patches, "ai_calls_used": 0})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the zero-AI Factory Safe Integrator E2E.")
    parser.add_argument("--fixture", default="career-consulting")
    parser.add_argument("--out", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    out = repo_path(args.out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    patch_specs = create_run(out)
    run_arg = rel(out)
    branch = f"factory/{out.name}/integration"
    worktree = f"workspace/factory-integration-worktrees/{out.name}"
    checks = [
        ("validate-plan", ["python3", "scripts/factory_plan.py", "validate", rel(out / "factory-plan.json")]),
        ("materialize", ["python3", "scripts/factory.py", "materialize", run_arg]),
        ("queue", ["python3", "scripts/factory.py", "queue", run_arg]),
    ]
    results = [run_step(name, command) for name, command in checks]
    create_patch_bundles(out, patch_specs)
    more_checks = [
        ("integrate-plan", ["python3", "scripts/factory.py", "integrate", run_arg, "--plan"]),
        ("prepare-branch", ["python3", "scripts/factory.py", "integrate", run_arg, "--prepare-branch", "--branch", branch, "--worktree", worktree]),
        ("apply-validate-each", ["python3", "scripts/factory.py", "integrate", run_arg, "--apply", "--validate-each", "--limit", "3", "--worktree", worktree]),
        ("validate-integrated", ["python3", "scripts/factory.py", "validate-integrated", run_arg]),
        ("release-candidate", ["python3", "scripts/factory.py", "release-candidate", run_arg]),
        ("sync-taskstream", ["python3", "scripts/factory.py", "sync-taskstream", run_arg, "--dry-run"]),
        ("render-hub", ["python3", "scripts/factory.py", "render-hub", run_arg]),
        ("state-validate", ["python3", "scripts/factory_integration_state.py", "validate", rel(out / "integration" / "integration-state.json")]),
    ]
    results.extend(run_step(name, command) for name, command in more_checks)
    total_duration_ms = round(sum(float(item["duration_ms"]) for item in results), 3)
    decision = "approve" if all(item["passed"] for item in results) else "blocked"
    summary = {
        "schema_version": "factory-integration-e2e-summary/v1",
        "fixture": args.fixture,
        "run_dir": run_arg,
        "decision": decision,
        "checks": results,
        "stats": {
            "total_duration_ms": total_duration_ms,
            "ai_calls_used": 0,
            "estimated_ai_cost_usd": 0,
            "validated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        },
    }
    write_json(out / "e2e-summary.json", summary)
    (out / "e2e-summary.md").write_text(
        "\n".join(
            [
                "# Factory Integration Zero-AI E2E",
                "",
                f"- Fixture: `{args.fixture}`",
                f"- Decision: `{decision}`",
                f"- Total duration ms: `{total_duration_ms}`",
                "- AI calls used: 0",
                "",
                "## Checks",
                "",
                *[f"- {'PASS' if item['passed'] else 'FAIL'} `{item['name']}` in `{item['duration_ms']}` ms" for item in results],
                "",
            ]
        ),
        encoding="utf-8",
    )
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"decision: {decision}")
        print(f"total_duration_ms: {total_duration_ms}")
        print("AI calls used: 0")
        print(f"summary: {rel(out / 'e2e-summary.md')}")
    return 0 if decision == "approve" else 1


if __name__ == "__main__":
    raise SystemExit(main())
