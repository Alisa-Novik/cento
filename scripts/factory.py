#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import factory_plan
import factory_render
import story_manifest
import validation_manifest


ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = ROOT / "workspace" / "runs" / "factory"


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:80] or "factory-run"


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


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"Expected object JSON: {path}")
    return payload


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    items: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            items.append(payload)
    return items


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def load_plan(run_dir: Path) -> dict[str, Any]:
    plan = read_json(run_dir / "factory-plan.json")
    errors = factory_plan.validate_plan(plan)
    if errors:
        raise SystemExit("Invalid factory plan:\n" + "\n".join(f"- {error}" for error in errors))
    return plan


def task_index(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(task.get("id")): task for task in plan.get("tasks") or [] if isinstance(task, dict)}


def queue_dir(run_dir: Path) -> Path:
    return run_dir / "queue"


def issue_map_path(run_dir: Path) -> Path:
    return run_dir / "taskstream-issues.json"


def validate_materialized(run_dir: Path, plan: dict[str, Any]) -> list[dict[str, str]]:
    outputs = []
    for task_id in task_index(plan):
        story_path = run_dir / "tasks" / task_id / "story.json"
        validation_path = run_dir / "tasks" / task_id / "validation.json"
        if not story_path.exists() or not validation_path.exists():
            raise SystemExit(f"Task {task_id} is not materialized; expected story.json and validation.json.")
        story = story_manifest.load_manifest(story_path)
        story_errors = story_manifest.validate_manifest(story, check_links=False)
        if story_errors:
            raise SystemExit(f"Invalid story for {task_id}:\n" + "\n".join(f"- {error}" for error in story_errors))
        validation = validation_manifest.load_validation(validation_path)
        validation_errors = validation_manifest.validate_validation_manifest(validation)
        if validation_errors:
            raise SystemExit(f"Invalid validation manifest for {task_id}:\n" + "\n".join(f"- {error}" for error in validation_errors))
        outputs.append({"task": task_id, "story": rel(story_path), "validation": rel(validation_path)})
    return outputs


def agent_work_role(lane: str) -> str:
    if lane in {"builder", "validator", "coordinator"}:
        return lane
    if lane == "docs-evidence":
        return "validator"
    return "builder"


def run_command(command: list[str]) -> dict[str, Any]:
    started = time.perf_counter()
    proc = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return {
        "command": command,
        "exit_code": proc.returncode,
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def run_id_from_request(request: str) -> str:
    return f"{slugify(request)}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"


def normalize_goal(request: str) -> str:
    request = " ".join(request.split())
    if not request:
        return "Create a validated Cento module plan."
    if "career" in request.lower() and "consult" in request.lower():
        return "Plan a Cento career consulting module with CRM, funnel, intake, docs, validation, and evidence surfaces."
    return f"Plan Cento implementation work for: {request}"


def package_from_request(request: str) -> str:
    if "career" in request.lower() and "consult" in request.lower():
        return "career-consulting-module-v1"
    return f"{slugify(request)}-v1"


def command_intake(args: argparse.Namespace) -> int:
    request = args.request.strip()
    if not request:
        print("ERROR: request must be non-empty", file=sys.stderr)
        return 1
    run_dir = repo_path(args.out) if args.out else RUN_ROOT / run_id_from_request(request)
    run_id = run_dir.name
    run_dir.mkdir(parents=True, exist_ok=True)
    normalized_goal = normalize_goal(request)
    package = args.package or package_from_request(request)
    intake = {
        "schema_version": "factory-intake/v1",
        "run_id": run_id,
        "request": {
            "raw": request,
            "normalized_goal": normalized_goal,
        },
        "package": package,
        "mode": "plan_only",
        "risk": args.risk,
        "created_at": now_iso(),
        "ai_calls_used": 0,
        "estimated_ai_cost_usd": 0,
    }
    constraints = {
        "schema_version": "factory-constraints/v1",
        "mode": "plan_only",
        "must_not_dispatch_workers": True,
        "max_strong_model_calls_per_factory_run": 0 if args.no_model else 1,
        "max_ai_calls_per_task": 0,
        "required_outputs": [
            "factory-plan.json",
            "tasks/*/story.json",
            "tasks/*/validation.json",
            "start-here.html",
            "implementation-map.html",
        ],
    }
    context_pack = {
        "schema_version": "factory-context-pack/v1",
        "run_id": run_id,
        "repo_facts": {
            "root": str(ROOT),
            "tool_registry": "data/tools.json",
            "story_manifest_tool": "scripts/story_manifest.py",
            "validation_manifest_tool": "scripts/validation_manifest.py",
        },
        "constraints": constraints,
        "known_gaps": [
            "Live worker dispatch is deliberately out of scope for factory-planning-v1.",
        ],
    }
    (run_dir / "request.md").write_text(f"# Factory Request\n\n{request}\n", encoding="utf-8")
    write_json(run_dir / "intake.json", intake)
    write_json(run_dir / "constraints.json", constraints)
    write_json(run_dir / "context-pack.json", context_pack)
    (run_dir / "context-pack.md").write_text(
        "\n".join(
            [
                "# Factory Context Pack",
                "",
                f"- Run: `{run_id}`",
                f"- Package: `{package}`",
                f"- Goal: {normalized_goal}",
                "- Dispatch: disabled",
                "- AI calls used: `0`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (run_dir / "missing-inputs.md").write_text("# Missing Inputs\n\n- None for deterministic plan-only slice.\n", encoding="utf-8")
    result = {"run_id": run_id, "run_dir": rel(run_dir), "intake": rel(run_dir / "intake.json")}
    print(json.dumps(result, indent=2, sort_keys=True) if args.json else rel(run_dir))
    return 0


def career_consulting_tasks(run_dir: Path, package: str) -> list[dict[str, Any]]:
    base = rel(run_dir)
    return [
        {
            "id": "crm-schema-extension",
            "title": "CRM schema extension plan",
            "lane": "builder",
            "node": "linux",
            "owned_scope": ["data/profiles/career-consulting.json", "workspace/runs/factory/"],
            "goal": "Plan CRM data surfaces for career consulting contacts, services, deals, and intake state.",
            "expected_outputs": [{"path": f"{base}/tasks/crm-schema-extension/evidence.md", "description": "CRM schema planning evidence"}],
            "validation_commands": ["python3 -m json.tool {run_dir}/tasks/crm-schema-extension/validation.json"],
            "no_model_eligible": True,
            "risk": "low",
            "dependencies": [],
        },
        {
            "id": "career-commands",
            "title": "Career consulting command plan",
            "lane": "builder",
            "node": "linux",
            "owned_scope": ["scripts/crm_module.py"],
            "goal": "Plan `cento crm career ...` command surface without implementing live dispatch.",
            "expected_outputs": [{"path": f"{base}/tasks/career-commands/evidence.md", "description": "Command planning evidence"}],
            "validation_commands": ["python3 -m json.tool {run_dir}/tasks/career-commands/validation.json"],
            "no_model_eligible": True,
            "risk": "medium",
            "dependencies": ["crm-schema-extension"],
        },
        {
            "id": "consulting-ui-route",
            "title": "Consulting Console UI route plan",
            "lane": "builder",
            "node": "macos",
            "owned_scope": ["templates/agent-work-app/index.html", "templates/agent-work-app/app.js", "templates/agent-work-app/styles.css"],
            "goal": "Plan the consulting UI route, screenshots, and validation evidence for the career module.",
            "expected_outputs": [{"path": f"{base}/tasks/consulting-ui-route/evidence.md", "description": "UI route planning evidence"}],
            "validation_commands": ["python3 -m json.tool {run_dir}/tasks/consulting-ui-route/validation.json"],
            "no_model_eligible": True,
            "risk": "medium",
            "dependencies": ["career-commands"],
        },
        {
            "id": "factory-docs-registry",
            "title": "Docs and registry alignment plan",
            "lane": "docs-evidence",
            "node": "linux",
            "owned_scope": ["data/tools.json", "data/cento-cli.json", "docs/factory.md", "docs/tool-index.md", "docs/platform-support.md", "README.md"],
            "goal": "Plan docs and registry updates needed for generated factory work.",
            "expected_outputs": [{"path": f"{base}/tasks/factory-docs-registry/evidence.md", "description": "Docs planning evidence"}],
            "validation_commands": ["python3 -m json.tool {run_dir}/tasks/factory-docs-registry/validation.json"],
            "no_model_eligible": True,
            "risk": "low",
            "dependencies": ["career-commands"],
        },
        {
            "id": "integration-release-packet",
            "title": "Integration and release packet plan",
            "lane": "validator",
            "node": "linux",
            "owned_scope": ["workspace/runs/factory/"],
            "goal": "Plan final validation summary, release notes, implementation map, and residual risk packet.",
            "expected_outputs": [{"path": f"{base}/tasks/integration-release-packet/evidence.md", "description": "Release packet planning evidence"}],
            "validation_commands": ["python3 -m json.tool {run_dir}/tasks/integration-release-packet/validation.json"],
            "no_model_eligible": True,
            "risk": "low",
            "dependencies": ["consulting-ui-route", "factory-docs-registry"],
        },
    ]


def generic_tasks(run_dir: Path, package: str) -> list[dict[str, Any]]:
    base = rel(run_dir)
    return [
        {
            "id": "module-plan",
            "title": "Module implementation plan",
            "lane": "builder",
            "node": "linux",
            "owned_scope": ["workspace/runs/factory/"],
            "goal": "Create a validated module implementation plan.",
            "expected_outputs": [{"path": f"{base}/tasks/module-plan/evidence.md", "description": "Module planning evidence"}],
            "validation_commands": ["python3 -m json.tool {run_dir}/tasks/module-plan/validation.json"],
            "no_model_eligible": True,
            "risk": "low",
            "dependencies": [],
        }
    ]


def command_plan(args: argparse.Namespace) -> int:
    run_dir = repo_path(args.run_dir)
    intake = read_json(run_dir / "intake.json")
    request = str((intake.get("request") or {}).get("raw") or "")
    package = str(intake.get("package") or package_from_request(request))
    tasks = career_consulting_tasks(run_dir, package) if "career" in request.lower() and "consult" in request.lower() else generic_tasks(run_dir, package)
    plan = {
        "schema_version": "factory-plan/v1",
        "run_id": str(intake.get("run_id") or run_dir.name),
        "request": intake.get("request") or {},
        "package": package,
        "mode": "plan_only",
        "risk": str(intake.get("risk") or "medium"),
        "budget": {
            "ai_call_budget": 0 if args.no_model else 1,
            "estimated_cost_usd": 0,
            "strong_model_calls_allowed": 0 if args.no_model else 1,
            "cheap_worker_calls_allowed": 0,
        },
        "shared_paths": ["workspace/runs/factory/"],
        "tasks": tasks,
        "integration": {
            "strategy": "plan_only_patch_queue",
            "merge_order": [task["id"] for task in tasks],
            "required_docs": ["README.md", "docs/tool-index.md", "docs/platform-support.md", "docs/factory.md"],
        },
        "validation": {
            "minimum_tier": "tier0",
            "requires_screenshots": True,
            "requires_api_smoke": False,
            "requires_human_review": False,
        },
        "evidence": {
            "run_dir": rel(run_dir),
            "summary": rel(run_dir / "summary.md"),
        },
        "created_at": now_iso(),
    }
    write_json(run_dir / "factory-plan.json", plan)
    errors = factory_plan.validate_plan(plan)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"factory_plan": rel(run_dir / "factory-plan.json"), "tasks": len(tasks)}, indent=2, sort_keys=True) if args.json else rel(run_dir / "factory-plan.json"))
    return 0


def story_for_task(plan: dict[str, Any], task: dict[str, Any], task_dir: Path) -> dict[str, Any]:
    validation_path = task_dir / "validation.json"
    deliverables_path = task_dir / "deliverables.json"
    hub_path = task_dir / "start-here.html"
    commands = [
        str(command).replace("{run_dir}", rel(repo_path((plan.get("evidence") or {}).get("run_dir") or task_dir.parent)))
        for command in task.get("validation_commands") or []
    ]
    return {
        "schema_version": "1.0",
        "issue": {
            "id": 0,
            "title": str(task.get("title") or task.get("id")),
            "package": str(plan.get("package") or "factory-planning-v1"),
        },
        "lane": {
            "owner": str(task.get("lane") or "builder"),
            "node": str(task.get("node") or "linux"),
            "agent": "",
            "role": str(task.get("lane") or "builder") if str(task.get("lane") or "builder") in story_manifest.VALID_ROLES else "builder",
        },
        "paths": {"run_dir": rel(task_dir)},
        "scope": {
            "goal": str(task.get("goal") or ""),
            "acceptance": [
                "Factory-generated story manifest validates.",
                "Factory-generated validation manifest validates.",
                "Plan-only task has durable evidence paths and no worker dispatch.",
            ],
        },
        "expected_outputs": [
            {
                **output,
                "owner": output.get("owner") or str(task.get("lane") or "builder"),
                "required": output.get("required", True),
            }
            if isinstance(output, dict)
            else {"path": str(output), "description": "Factory expected output", "owner": str(task.get("lane") or "builder"), "required": True}
            for output in task.get("expected_outputs") or []
        ],
        "validation": {
            "manifest": rel(validation_path),
            "mode": "no-model" if task.get("no_model_eligible") else "manual-planning",
            "risk": str(task.get("risk") or "low"),
            "no_model_eligible": bool(task.get("no_model_eligible")),
            "escalation_triggers": ["missing_manifest", "failed_deterministic_command", "ambiguity"],
            "commands": commands or [f"python3 -m json.tool {rel(validation_path)}"],
        },
        "deliverables": {
            "manifest": rel(deliverables_path),
            "hub": rel(hub_path),
        },
        "review_gate": {
            "required_sections": ["Delivered", "Validation", "Evidence", "Residual risk"],
            "residual_risk_required": True,
        },
        "metadata": {
            "factory_run_id": str(plan.get("run_id") or ""),
            "factory_task_id": str(task.get("id") or ""),
            "generated_at": now_iso(),
        },
    }


def materialize_run(run_dir: Path) -> dict[str, Any]:
    plan = read_json(run_dir / "factory-plan.json")
    errors = factory_plan.validate_plan(plan)
    if errors:
        raise SystemExit("Invalid factory plan:\n" + "\n".join(f"- {error}" for error in errors))
    outputs: list[dict[str, str]] = []
    for task in plan.get("tasks") or []:
        task_id = str(task.get("id") or "")
        task_dir = run_dir / "tasks" / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        story = story_for_task(plan, task, task_dir)
        story_path = task_dir / "story.json"
        write_json(story_path, story)
        story_errors = story_manifest.validate_manifest(story, check_links=False)
        if story_errors:
            raise SystemExit(f"Invalid generated story for {task_id}:\n" + "\n".join(f"- {error}" for error in story_errors))
        validation = validation_manifest.build_manifest(story, story_path)
        validation_path = task_dir / "validation.json"
        write_json(validation_path, validation)
        validation_errors = validation_manifest.validate_validation_manifest(validation)
        if validation_errors:
            raise SystemExit(f"Invalid generated validation for {task_id}:\n" + "\n".join(f"- {error}" for error in validation_errors))
        outputs.append({"task": task_id, "story": rel(story_path), "validation": rel(validation_path)})
    write_json(run_dir / "materialize-summary.json", {"generated_at": now_iso(), "tasks": outputs, "ai_calls_used": 0, "estimated_ai_cost_usd": 0})
    return {"tasks": outputs}


def command_materialize(args: argparse.Namespace) -> int:
    run_dir = repo_path(args.run_dir)
    result = materialize_run(run_dir)
    print(json.dumps(result, indent=2, sort_keys=True) if args.json else rel(run_dir / "materialize-summary.json"))
    return 0


def command_create_issues(args: argparse.Namespace) -> int:
    run_dir = repo_path(args.run_dir)
    plan = load_plan(run_dir)
    validate_materialized(run_dir, plan)
    tasks = []
    for task in plan.get("tasks") or []:
        task_id = str(task.get("id") or "")
        story_path = run_dir / "tasks" / task_id / "story.json"
        role = agent_work_role(str(task.get("lane") or "builder"))
        tasks.append(
            {
                "title": str(task.get("title") or task_id),
                "package": str(plan.get("package") or ""),
                "lane": str(task.get("lane") or ""),
                "node": str(task.get("node") or ""),
                "role": role,
                "story_manifest": rel(story_path),
                "command": " ".join(
                    [
                        "cento",
                        "agent-work",
                        "create",
                        "--title",
                        shlex.quote(str(task.get("title") or task_id)),
                        "--manifest",
                        shlex.quote(rel(story_path)),
                        "--package",
                        shlex.quote(str(plan.get("package") or "")),
                        "--node",
                        shlex.quote(str(task.get("node") or "")),
                        "--role",
                        shlex.quote(role),
                    ]
                ),
            }
        )
    preview = {
        "schema_version": "factory-create-issues-preview/v1",
        "dry_run": not args.apply,
        "package": str(plan.get("package") or ""),
        "tasks": tasks,
        "ai_calls_used": 0,
        "estimated_ai_cost_usd": 0,
        "generated_at": now_iso(),
    }
    write_json(run_dir / "create-issues-preview.json", preview)

    if not args.apply:
        print(json.dumps(preview, indent=2, sort_keys=True))
        return 0

    existing = read_json(issue_map_path(run_dir)) if issue_map_path(run_dir).exists() and not args.force else {}
    if existing.get("created") and not args.force:
        print(json.dumps(existing, indent=2, sort_keys=True))
        return 0

    created: list[dict[str, Any]] = []
    epic_story = story_for_task(
        plan,
        {
            "id": "factory-epic",
            "title": f"EPIC: {plan.get('package')}",
            "lane": "coordinator",
            "node": "linux",
            "goal": str((plan.get("request") or {}).get("normalized_goal") or "Deliver the factory package."),
            "expected_outputs": [{"path": rel(run_dir / "delivery-status.json"), "description": "Factory delivery status", "owner": "coordinator"}],
            "validation_commands": [f"python3 scripts/factory.py release {rel(run_dir)} --json"],
            "no_model_eligible": True,
            "risk": str(plan.get("risk") or "medium"),
        },
        run_dir / "tasks" / "factory-epic",
    )
    epic_dir = run_dir / "tasks" / "factory-epic"
    epic_dir.mkdir(parents=True, exist_ok=True)
    epic_story_path = epic_dir / "story.json"
    write_json(epic_story_path, epic_story)
    epic_cmd = [
        "python3",
        "scripts/agent_work.py",
        "create",
        "--title",
        f"EPIC: {plan.get('package')}",
        "--manifest",
        rel(epic_story_path),
        "--package",
        str(plan.get("package") or ""),
        "--node",
        "linux",
        "--role",
        "coordinator",
        "--epic",
        "--description",
        f"Factory run: {rel(run_dir)}",
        "--json",
    ]
    epic_result = run_command(epic_cmd)
    if epic_result["exit_code"] != 0:
        raise SystemExit(epic_result["stderr"] or epic_result["stdout"] or "failed to create factory epic")
    epic_payload = json.loads(epic_result["stdout"])
    created.append({"task": "factory-epic", "issue": epic_payload.get("id"), "role": "coordinator", "duration_ms": epic_result["duration_ms"]})

    for item in tasks:
        command = [
            "python3",
            "scripts/agent_work.py",
            "create",
            "--title",
            str(item["title"]),
            "--manifest",
            str(item["story_manifest"]),
            "--package",
            str(item["package"]),
            "--node",
            str(item["node"]),
            "--role",
            str(item["role"]),
            "--description",
            f"Factory task from {rel(run_dir)}. Epic issue: #{epic_payload.get('id')}",
            "--json",
        ]
        result = run_command(command)
        if result["exit_code"] != 0:
            raise SystemExit(result["stderr"] or result["stdout"] or f"failed to create task {item['title']}")
        payload = json.loads(result["stdout"])
        created.append({"task": str(Path(item["story_manifest"]).parent.name), "issue": payload.get("id"), "role": item["role"], "duration_ms": result["duration_ms"]})

    issue_map = {
        "schema_version": "factory-taskstream-issues/v1",
        "created": True,
        "dry_run": False,
        "package": str(plan.get("package") or ""),
        "run_dir": rel(run_dir),
        "issues": created,
        "stats": {
            "total_duration_ms": round(sum(float(item["duration_ms"]) for item in created), 3),
            "ai_calls_used": 0,
            "estimated_ai_cost_usd": 0,
            "created_at": now_iso(),
        },
    }
    write_json(issue_map_path(run_dir), issue_map)
    print(json.dumps(issue_map, indent=2, sort_keys=True))
    return 0


def command_preflight(args: argparse.Namespace) -> int:
    run_dir = repo_path(args.run_dir)
    plan = load_plan(run_dir)
    validate_materialized(run_dir, plan)
    manager = subprocess.run(["python3", "scripts/agent_manager.py", "scan", "--json"], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    manager_payload: dict[str, Any] = {}
    if manager.returncode == 0:
        try:
            decoded = json.loads(manager.stdout)
            manager_payload = decoded if isinstance(decoded, dict) else {}
        except json.JSONDecodeError:
            manager_payload = {}
    summary = manager_payload.get("summary") if isinstance(manager_payload.get("summary"), dict) else {}
    warnings = []
    actionable_stale = int(summary.get("actionable_stale", 0) or 0)
    risk_count = int(summary.get("risk_count", 0) or 0)
    if actionable_stale > args.max_actionable_stale:
        warnings.append(f"actionable stale runs {actionable_stale} exceeds threshold {args.max_actionable_stale}")
    if risk_count > args.max_risk_count:
        warnings.append(f"manager risk count {risk_count} exceeds threshold {args.max_risk_count}")
    payload = {
        "schema_version": "factory-preflight/v1",
        "run_dir": rel(run_dir),
        "agent_manager_exit_code": manager.returncode,
        "agent_manager_available": manager.returncode == 0,
        "blocked": manager.returncode != 0 or bool(warnings),
        "reason": "; ".join(warnings) if warnings else "" if manager.returncode == 0 else (manager.stderr.strip() or manager.stdout.strip()[-500:]),
        "manager_summary": summary,
        "tasks": len(plan.get("tasks") or []),
        "ai_calls_used": 0,
        "estimated_ai_cost_usd": 0,
    }
    write_json(run_dir / "preflight.json", payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not payload["blocked"] else 1


def command_render_hub(args: argparse.Namespace) -> int:
    outputs = factory_render.render_run(repo_path(args.run_dir))
    print(json.dumps(outputs, indent=2, sort_keys=True) if args.json else outputs["start_hub"])
    return 0


def build_queue(run_dir: Path) -> dict[str, Any]:
    plan = load_plan(run_dir)
    validate_materialized(run_dir, plan)
    qdir = queue_dir(run_dir)
    qdir.mkdir(parents=True, exist_ok=True)
    tasks = task_index(plan)
    queued: list[dict[str, Any]] = []
    waiting: list[dict[str, Any]] = []
    owned_paths: dict[str, str] = {}
    for task_id, task in tasks.items():
        deps = [str(dep) for dep in task.get("dependencies") or []]
        record = {
            "task_id": task_id,
            "title": str(task.get("title") or task_id),
            "lane": str(task.get("lane") or "builder"),
            "node": str(task.get("node") or "linux"),
            "dependencies": deps,
            "owned_scope": [str(path) for path in task.get("owned_scope") or []],
            "status": "queued" if not deps else "waiting",
            "story_manifest": rel(run_dir / "tasks" / task_id / "story.json"),
            "validation_manifest": rel(run_dir / "tasks" / task_id / "validation.json"),
        }
        for owned in record["owned_scope"]:
            owned_paths[owned] = task_id
        (queued if not deps else waiting).append(record)
    state = {
        "schema_version": "factory-queue/v1",
        "run_dir": rel(run_dir),
        "package": str(plan.get("package") or ""),
        "generated_at": now_iso(),
        "merge_order": [str(item) for item in (plan.get("integration") or {}).get("merge_order") or tasks.keys()],
        "tasks": {item["task_id"]: item for item in [*queued, *waiting]},
        "stats": {
            "queued": len(queued),
            "waiting": len(waiting),
            "leased": 0,
            "done": 0,
            "blocked": 0,
            "ai_calls_used": 0,
            "estimated_ai_cost_usd": 0,
        },
    }
    write_jsonl(qdir / "queued.jsonl", queued)
    write_jsonl(qdir / "waiting.jsonl", waiting)
    write_jsonl(qdir / "leased.jsonl", [])
    write_jsonl(qdir / "validating.jsonl", [])
    write_jsonl(qdir / "blocked.jsonl", [])
    write_jsonl(qdir / "done.jsonl", [])
    write_jsonl(qdir / "deadletter.jsonl", [])
    write_json(qdir / "owned-paths.json", {"schema_version": "factory-owned-paths/v1", "paths": owned_paths})
    write_json(qdir / "state.json", state)
    return state


def command_queue(args: argparse.Namespace) -> int:
    state = build_queue(repo_path(args.run_dir))
    print(json.dumps(state, indent=2, sort_keys=True) if args.json else rel(queue_dir(repo_path(args.run_dir)) / "state.json"))
    return 0


def load_queue_state(run_dir: Path) -> dict[str, Any]:
    state_path = queue_dir(run_dir) / "state.json"
    return read_json(state_path) if state_path.exists() else build_queue(run_dir)


def runnable_tasks(state: dict[str, Any], *, lane: str = "", include_waiting: bool = False) -> list[dict[str, Any]]:
    tasks = state.get("tasks") if isinstance(state.get("tasks"), dict) else {}
    done = {task_id for task_id, item in tasks.items() if isinstance(item, dict) and item.get("status") == "done"}
    runnable = []
    ordered_ids = [str(item) for item in state.get("merge_order") or tasks.keys()]
    for task_id in ordered_ids:
        item = tasks.get(task_id)
        if not isinstance(item, dict):
            continue
        if lane and str(item.get("lane") or "") != lane:
            continue
        status = str(item.get("status") or "")
        deps = [str(dep) for dep in item.get("dependencies") or []]
        if status == "queued" or include_waiting or all(dep in done for dep in deps):
            runnable.append(item)
    return runnable


def command_dispatch(args: argparse.Namespace) -> int:
    run_dir = repo_path(args.run_dir)
    preflight_args = argparse.Namespace(
        run_dir=str(run_dir),
        json=True,
        max_actionable_stale=args.max_actionable_stale,
        max_risk_count=args.max_risk_count,
    )
    preflight_result = command_preflight(preflight_args)
    if preflight_result != 0:
        return preflight_result
    state = load_queue_state(run_dir)
    selected = runnable_tasks(state, lane=args.lane, include_waiting=args.include_waiting)[: args.max]
    issue_map = read_json(issue_map_path(run_dir)) if issue_map_path(run_dir).exists() else {}
    issue_lookup = {
        str(item.get("task")): item.get("issue")
        for item in issue_map.get("issues", [])
        if isinstance(item, dict)
    }
    leases = []
    for item in selected:
        task_id = str(item.get("task_id"))
        lease = {
            "lease_id": f"lease-{task_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            "task_id": task_id,
            "issue_id": issue_lookup.get(task_id),
            "lane": str(item.get("lane") or ""),
            "node": str(item.get("node") or ""),
            "owned_scope": item.get("owned_scope") or [],
            "story_manifest": item.get("story_manifest"),
            "validation_manifest": item.get("validation_manifest"),
            "status": "planned" if args.dry_run else "leased",
            "dry_run": bool(args.dry_run),
            "created_at": now_iso(),
            "dispatch_command": (
                f"cento agent-work dispatch {issue_lookup.get(task_id)} --node {shlex.quote(str(item.get('node') or ''))} --dry-run"
                if issue_lookup.get(task_id)
                else "blocked: create Taskstream issues before live dispatch"
            ),
        }
        leases.append(lease)
    qdir = queue_dir(run_dir)
    existing_leases = read_jsonl(qdir / "leased.jsonl")
    write_jsonl(qdir / "leased.jsonl", [*existing_leases, *leases])
    dispatch_plan = {
        "schema_version": "factory-dispatch-plan/v1",
        "run_dir": rel(run_dir),
        "dry_run": bool(args.dry_run),
        "lane": args.lane,
        "max": args.max,
        "selected": leases,
        "blocked_reason": "" if selected else "no runnable tasks matched lane/dependency filters",
        "ai_calls_used": 0,
        "estimated_ai_cost_usd": 0,
        "generated_at": now_iso(),
    }
    write_json(run_dir / "dispatch-plan.json", dispatch_plan)
    print(json.dumps(dispatch_plan, indent=2, sort_keys=True))
    return 0


def command_integrate(args: argparse.Namespace) -> int:
    run_dir = repo_path(args.run_dir)
    plan = load_plan(run_dir)
    validate_materialized(run_dir, plan)
    patches_dir = run_dir / "patches"
    entries = []
    for task_id in (plan.get("integration") or {}).get("merge_order") or []:
        patch_path = patches_dir / str(task_id) / "patch.diff"
        validation_path = run_dir / "tasks" / str(task_id) / "validation.json"
        entries.append(
            {
                "task_id": str(task_id),
                "patch": rel(patch_path) if patch_path.exists() else "",
                "patch_available": patch_path.exists(),
                "validation_manifest": rel(validation_path),
                "decision": "ready_for_patch_validation" if patch_path.exists() else "no_patch_plan_only",
            }
        )
    integration = {
        "schema_version": "factory-integration-plan/v1",
        "run_dir": rel(run_dir),
        "dry_run": bool(args.dry_run),
        "strategy": str((plan.get("integration") or {}).get("strategy") or "patch_queue"),
        "entries": entries,
        "decision": "approve_plan_only" if all(not item["patch_available"] for item in entries) else "needs_patch_validation",
        "ai_calls_used": 0,
        "estimated_ai_cost_usd": 0,
        "generated_at": now_iso(),
    }
    write_json(run_dir / "integration-plan.json", integration)
    print(json.dumps(integration, indent=2, sort_keys=True))
    return 0


def delivery_status(run_dir: Path) -> dict[str, Any]:
    expected = {
        "intake": run_dir / "intake.json",
        "factory_plan": run_dir / "factory-plan.json",
        "materialize_summary": run_dir / "materialize-summary.json",
        "queue_state": queue_dir(run_dir) / "state.json",
        "dispatch_plan": run_dir / "dispatch-plan.json",
        "integration_plan": run_dir / "integration-plan.json",
        "start_hub": run_dir / "start-here.html",
        "implementation_map": run_dir / "implementation-map.html",
        "validation_summary": run_dir / "validation-summary.json",
    }
    files = {name: path.exists() for name, path in expected.items()}
    summary = read_json(run_dir / "validation-summary.json") if (run_dir / "validation-summary.json").exists() else {}
    decision = "delivered" if all(files.values()) else "incomplete"
    return {
        "schema_version": "factory-delivery-status/v1",
        "run_dir": rel(run_dir),
        "decision": decision,
        "files": files,
        "validation_decision": summary.get("decision", ""),
        "checks": len(summary.get("checks") or []),
        "stats": {
            "total_duration_ms": (summary.get("stats") or {}).get("total_duration_ms", 0),
            "ai_calls_used": 0,
            "estimated_ai_cost_usd": 0,
            "generated_at": now_iso(),
        },
    }


def command_release(args: argparse.Namespace) -> int:
    run_dir = repo_path(args.run_dir)
    factory_render.render_run(run_dir)
    status = delivery_status(run_dir)
    write_json(run_dir / "delivery-status.json", status)
    release_lines = [
        "# Factory Delivery Status",
        "",
        f"- Decision: `{status['decision']}`",
        f"- Run: `{status['run_dir']}`",
        f"- Validation decision: `{status['validation_decision'] or 'not recorded'}`",
        f"- Checks: `{status['checks']}`",
        "- AI calls used: `0`",
        "",
        "## Required Artifacts",
        "",
    ]
    for name, present in status["files"].items():
        release_lines.append(f"- {'PASS' if present else 'MISSING'} `{name}`")
    (run_dir / "project-delivery.md").write_text("\n".join(release_lines) + "\n", encoding="utf-8")
    print(json.dumps(status, indent=2, sort_keys=True) if args.json else rel(run_dir / "delivery-status.json"))
    return 0 if status["decision"] == "delivered" else 1


def command_status(args: argparse.Namespace) -> int:
    run_dir = repo_path(args.run_dir)
    files = {
        "intake": (run_dir / "intake.json").exists(),
        "plan": (run_dir / "factory-plan.json").exists(),
        "materialized": (run_dir / "materialize-summary.json").exists(),
        "queue": (queue_dir(run_dir) / "state.json").exists(),
        "dispatch_plan": (run_dir / "dispatch-plan.json").exists(),
        "integration_plan": (run_dir / "integration-plan.json").exists(),
        "hub": (run_dir / "start-here.html").exists(),
        "delivery_status": (run_dir / "delivery-status.json").exists(),
    }
    payload = {"run_dir": rel(run_dir), "files": files, "delivery": delivery_status(run_dir) if (run_dir / "validation-summary.json").exists() else {}}
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Cento Factory workflow for manifest-driven planning, queueing, dry-run dispatch, integration gates, and release evidence.")
    sub = parser.add_subparsers(dest="command", required=True)

    intake = sub.add_parser("intake", help="Create request, intake, constraints, and context-pack artifacts.")
    intake.add_argument("request")
    intake.add_argument("--out", default="")
    intake.add_argument("--package", default="")
    intake.add_argument("--risk", choices=["low", "medium", "high"], default="medium")
    intake.add_argument("--dry-run", action="store_true", help="Compatibility flag; artifacts are still written for inspection.")
    intake.add_argument("--no-model", action="store_true", default=True)
    intake.add_argument("--json", action="store_true")
    intake.set_defaults(func=command_intake)

    plan = sub.add_parser("plan", help="Generate deterministic factory-plan.json from intake artifacts.")
    plan.add_argument("run_dir")
    plan.add_argument("--no-model", action="store_true", default=True)
    plan.add_argument("--json", action="store_true")
    plan.set_defaults(func=command_plan)

    materialize = sub.add_parser("materialize", help="Generate story.json and validation.json per task.")
    materialize.add_argument("run_dir")
    materialize.add_argument("--json", action="store_true")
    materialize.set_defaults(func=command_materialize)

    create_issues = sub.add_parser("create-issues", help="Preview or apply Taskstream issue creation from generated manifests.")
    create_issues.add_argument("run_dir")
    create_issues.add_argument("--dry-run", action="store_true", default=True)
    create_issues.add_argument("--apply", action="store_true", help="Create Taskstream issues. Default is preview only.")
    create_issues.add_argument("--force", action="store_true", help="Recreate issue map even if taskstream-issues.json exists.")
    create_issues.set_defaults(func=command_create_issues)

    preflight = sub.add_parser("preflight", help="Run plan-only factory safety preflight.")
    preflight.add_argument("run_dir")
    preflight.add_argument("--json", action="store_true")
    preflight.add_argument("--max-actionable-stale", type=int, default=8)
    preflight.add_argument("--max-risk-count", type=int, default=10)
    preflight.set_defaults(func=command_preflight)

    queue = sub.add_parser("queue", help="Create deterministic queue, dependency, and owned-path ledgers.")
    queue.add_argument("run_dir")
    queue.add_argument("--json", action="store_true")
    queue.set_defaults(func=command_queue)

    dispatch = sub.add_parser("dispatch", help="Plan runnable work and write lease records without launching AI by default.")
    dispatch.add_argument("run_dir")
    dispatch.add_argument("--lane", default="")
    dispatch.add_argument("--max", type=int, default=4)
    dispatch.add_argument("--dry-run", action="store_true", default=True)
    dispatch.add_argument("--include-waiting", action="store_true", help="Include tasks whose dependencies are not marked done.")
    dispatch.add_argument("--max-actionable-stale", type=int, default=8)
    dispatch.add_argument("--max-risk-count", type=int, default=10)
    dispatch.set_defaults(func=command_dispatch)

    integrate = sub.add_parser("integrate", help="Write patch queue integration plan and release gate metadata.")
    integrate.add_argument("run_dir")
    integrate.add_argument("--dry-run", action="store_true", default=True)
    integrate.set_defaults(func=command_integrate)

    release = sub.add_parser("release", help="Write final delivery status and project-delivery.md.")
    release.add_argument("run_dir")
    release.add_argument("--json", action="store_true")
    release.set_defaults(func=command_release)

    render = sub.add_parser("render-hub", help="Render start-here.html and implementation-map.html.")
    render.add_argument("run_dir")
    render.add_argument("--json", action="store_true")
    render.set_defaults(func=command_render_hub)

    status = sub.add_parser("status", help="Show factory run artifact status.")
    status.add_argument("run_dir")
    status.set_defaults(func=command_status)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
