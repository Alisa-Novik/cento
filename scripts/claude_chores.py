#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(os.environ.get("CENTO_ROOT", Path(__file__).resolve().parent.parent))
RUN_ROOT = ROOT / "workspace" / "runs" / "claude-chores"
STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "cento"
DOC_PATH = ROOT / "docs" / "claude-code-chores.md"
TOOLS_JSON = ROOT / "data" / "tools.json"
DEFAULT_PACKAGE = "claude-chores"
DEFAULT_RUNTIME = "claude-code"
DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_ACTIVE_TARGETS = {"builder": 2, "small": 1, "validator": 1, "coordinator": 0}
CRON_BEGIN = "# >>> cento claude-chores >>>"
CRON_END = "# <<< cento claude-chores <<<"
SCAN_ROOTS = ("scripts", "docs", "tests", "data")
TODO_PATTERN = re.compile(r"\b(?:TODO|FIXME)\s*:")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return slug[:80] or "chore"


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def write_json(path: Path, payload: dict[str, Any] | list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def command_result_payload(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    return {
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def run_command(command: list[str], *, env: dict[str, str] | None = None, timeout: int = 90) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )


def run_json_command(command: list[str], *, timeout: int = 45) -> dict[str, Any]:
    result = run_command(command, timeout=timeout)
    if result.returncode != 0:
        return {"error": result.stderr.strip() or result.stdout.strip(), "returncode": result.returncode}
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        return {"error": f"invalid JSON: {exc}", "returncode": result.returncode, "stdout": result.stdout.strip()}
    return payload if isinstance(payload, dict) else {}


def agent_work_issues() -> list[dict[str, Any]]:
    payload = run_json_command(["python3", "scripts/agent_work.py", "list", "--json"], timeout=30)
    issues = payload.get("issues")
    return issues if isinstance(issues, list) else []


def agent_work_active_runs(*, include_untracked: bool = True) -> list[dict[str, Any]]:
    command = ["python3", "scripts/agent_work.py", "runs", "--json", "--active"]
    if not include_untracked:
        command.append("--no-untracked")
    payload = run_json_command(command, timeout=20)
    runs = payload.get("runs")
    return runs if isinstance(runs, list) else []


def candidate_fingerprint(source: str, title: str, owned_paths: list[str]) -> str:
    seed = json.dumps({"source": source, "title": title, "owned_paths": sorted(owned_paths)}, sort_keys=True)
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]


def make_candidate(
    *,
    source: str,
    title: str,
    description: str,
    owned_paths: list[str],
    acceptance: list[str],
    validation_commands: list[str],
    priority: int,
) -> dict[str, Any]:
    paths = [path for path in dict.fromkeys(owned_paths) if path]
    fingerprint = candidate_fingerprint(source, title, paths)
    return {
        "fingerprint": fingerprint,
        "source": source,
        "title": title,
        "task_title": f"[chore:{fingerprint}] {title}",
        "description": description,
        "owned_paths": paths,
        "acceptance": acceptance,
        "validation_commands": validation_commands,
        "priority": priority,
        "package": DEFAULT_PACKAGE,
        "node": "linux",
        "agent": "claude-code",
        "role": "builder",
    }


def load_tools() -> list[dict[str, Any]]:
    payload = read_json(TOOLS_JSON)
    tools = payload.get("tools")
    return tools if isinstance(tools, list) else []


def discover_missing_entrypoint_chores() -> list[dict[str, Any]]:
    chores: list[dict[str, Any]] = []
    for tool in load_tools():
        entrypoint = str(tool.get("entrypoint") or "").strip()
        if not entrypoint or entrypoint.startswith("~"):
            continue
        entry_path = ROOT / entrypoint.removeprefix("./")
        if entry_path.exists():
            continue
        tool_id = str(tool.get("id") or "unknown")
        name = str(tool.get("name") or tool_id)
        chores.append(
            make_candidate(
                source=f"missing-entrypoint:{tool_id}",
                title=f"Restore registered {tool_id} entrypoint",
                description=(
                    f"The Cento registry declares `{entrypoint}` for `{tool_id}` ({name}), "
                    "but the file is missing. Restore the entrypoint or correct the registry/docs so "
                    "the command no longer fails at dispatch time."
                ),
                owned_paths=[rel(entry_path), "data/tools.json", "docs/tool-index.md"],
                acceptance=[
                    f"`cento {tool_id} --help` or an equivalent smoke path no longer fails because the entrypoint is missing.",
                    "Registry and docs describe the actual command surface.",
                ],
                validation_commands=[
                    f"test -e {shlex.quote(rel(entry_path))}",
                    f"./scripts/cento.sh docs {shlex.quote(tool_id)} >/tmp/cento-{slugify(tool_id)}-docs.txt",
                ],
                priority=10,
            )
        )
    return chores


def text_files_under(root_name: str) -> list[Path]:
    root = ROOT / root_name
    if not root.exists():
        return []
    paths: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in {".git", "node_modules", "__pycache__", ".pytest_cache"} for part in path.parts):
            continue
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".sqlite3", ".db", ".pyc"}:
            continue
        paths.append(path)
    return paths


def matching_files(pattern: str, *, roots: tuple[str, ...]) -> list[Path]:
    matches: list[Path] = []
    for root_name in roots:
        for path in text_files_under(root_name):
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if pattern in text:
                matches.append(path)
    return matches


def discover_docs_cli_drift_chores() -> list[dict[str, Any]]:
    paths = [rel(path) for path in matching_files("dispatch-pool", roots=("data", "docs"))]
    if not paths:
        return []
    return [
        make_candidate(
            source="docs-cli-drift:dispatch-pool",
            title="Remove stale agent-work dispatch-pool references",
            description=(
                "`agent-work` no longer exposes a `dispatch-pool` subcommand, but docs or registry "
                "text still references it. Replace stale references with the current `agent-pool-kick` "
                "or `agent-work dispatch` surface."
            ),
            owned_paths=paths,
            acceptance=[
                "No command-reference docs claim `cento agent-work dispatch-pool` is available.",
                "Replacement text points operators to a working native Cento dispatch path.",
            ],
            validation_commands=[
                "! rg -n 'agent-work dispatch-pool|dispatch-pool' data docs",
                "python3 -m json.tool data/tools.json >/tmp/cento-tools-json-check.txt",
            ],
            priority=20,
        )
    ]


def discover_todo_chores(limit: int = 5) -> list[dict[str, Any]]:
    chores: list[dict[str, Any]] = []
    for root_name in SCAN_ROOTS:
        for path in text_files_under(root_name):
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except UnicodeDecodeError:
                continue
            hits = [line.strip() for line in lines if TODO_PATTERN.search(line)]
            if not hits:
                continue
            path_text = rel(path)
            chores.append(
                make_candidate(
                    source=f"todo-hotspot:{path_text}",
                    title=f"Resolve TODO/FIXME hotspot in {path_text}",
                    description=(
                        f"`{path_text}` contains {len(hits)} TODO/FIXME marker(s). Resolve the stale marker, "
                        "convert it into a clearer tracked issue, or document why it must remain."
                    ),
                    owned_paths=[path_text],
                    acceptance=[
                        "The selected TODO/FIXME marker is resolved, clarified, or converted into explicit tracked follow-up.",
                        "The file remains syntactically valid for its format.",
                    ],
                    validation_commands=[f"test -s {shlex.quote(path_text)}"],
                    priority=60 + len(chores),
                )
            )
            if len(chores) >= limit:
                return chores
    return chores


def discover_blocked_queue_chores(issues: list[dict[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
    chores: list[dict[str, Any]] = []
    for issue in issues:
        if str(issue.get("status") or "") != "Blocked":
            continue
        issue_id = int(issue.get("id") or 0)
        if issue_id <= 0:
            continue
        title = str(issue.get("subject") or f"issue {issue_id}")
        chores.append(
            make_candidate(
                source=f"blocked-queue:{issue_id}",
                title=f"Repair blocked Taskstream issue {issue_id}",
                description=(
                    f"Review blocked Taskstream issue #{issue_id}: {title}. Identify whether it needs a "
                    "manifest repair, clearer owned paths, requeue note, or closure recommendation."
                ),
                owned_paths=[f"workspace/runs/agent-work/{issue_id}/"],
                acceptance=[
                    "A concise repair or closure recommendation is written into the issue/run evidence.",
                    "No unrelated Taskstream issues are modified.",
                ],
                validation_commands=[f"test -d workspace/runs/agent-work/{issue_id} || true"],
                priority=80 + len(chores),
            )
        )
        if len(chores) >= limit:
            break
    return chores


def discover_candidate_chores(scope: str, issues: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    issues = issues if issues is not None else agent_work_issues()
    candidates: list[dict[str, Any]] = []
    candidates.extend(discover_missing_entrypoint_chores())
    candidates.extend(discover_docs_cli_drift_chores())
    if scope == "broad-repo":
        candidates.extend(discover_todo_chores())
        candidates.extend(discover_blocked_queue_chores(issues))
    unique: dict[str, dict[str, Any]] = {}
    for item in candidates:
        unique.setdefault(str(item["fingerprint"]), item)
    return sorted(unique.values(), key=lambda item: (int(item.get("priority") or 999), str(item.get("title") or "")))


def open_chore_fingerprints(issues: list[dict[str, Any]]) -> dict[str, int]:
    fingerprints: dict[str, int] = {}
    for issue in issues:
        if str(issue.get("package") or "") != DEFAULT_PACKAGE:
            continue
        status = str(issue.get("status") or "")
        if status == "Done":
            continue
        subject = str(issue.get("subject") or "")
        match = re.search(r"\[chore:([0-9a-f]{12})\]", subject)
        if match:
            try:
                fingerprints[match.group(1)] = int(issue.get("id") or 0)
            except (TypeError, ValueError):
                fingerprints[match.group(1)] = 0
    return fingerprints


def annotate_existing(candidates: list[dict[str, Any]], issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    existing = open_chore_fingerprints(issues)
    annotated: list[dict[str, Any]] = []
    for item in candidates:
        clone = dict(item)
        issue_id = existing.get(str(item.get("fingerprint") or ""))
        clone["existing_issue_id"] = issue_id or None
        clone["eligible_to_create"] = issue_id is None
        annotated.append(clone)
    return annotated


def process_benefit_summary(active_runs: list[dict[str, Any]], issues: list[dict[str, Any]]) -> dict[str, Any]:
    untracked = [run for run in active_runs if str(run.get("run_id") or "").startswith("untracked-")]
    managed = [run for run in active_runs if run not in untracked]
    blocked = [issue for issue in issues if str(issue.get("status") or "") == "Blocked"]
    queued = [issue for issue in issues if str(issue.get("status") or "") == "Queued"]
    return {
        "active_run_count": len(active_runs),
        "managed_active_run_count": len(managed),
        "untracked_active_process_count": len(untracked),
        "queued_issue_count": len(queued),
        "blocked_issue_count": len(blocked),
        "benefits": [
            "keeps small repo-maintenance work moving without consuming metered OpenAI API budget",
            "turns discovered weak spots into scoped Taskstream items with validation manifests",
            "reduces manual queue grooming before Codex or Claude workers pick up larger work",
        ],
    }


def render_markdown(
    *,
    generated_at: str,
    scope: str,
    candidates: list[dict[str, Any]],
    created: list[dict[str, Any]],
    dispatch_summary: dict[str, Any],
    process_summary: dict[str, Any],
) -> str:
    lines = [
        "# Claude Code Chores",
        "",
        f"Generated: `{generated_at}`",
        "",
        "## Policy",
        "",
        "- Runtime: `claude-code`.",
        f"- Default model: `{DEFAULT_MODEL}`.",
        "- Controlled cron cadence: every 30 minutes.",
        "- Per tick: create at most 2 new chores and launch at most 2 Claude jobs.",
        "- Active targets: `builder=2`, `small=1`, `validator=1`, `coordinator=0`.",
        "- If Codex/Claude utilization is above 30%, prefer agent lanes for roughly 70-80% of eligible non-API-only work.",
        "- Metered OpenAI API work is not used by this chore loop.",
        "",
        "## Process Benefit Scan",
        "",
        f"- Active runs/processes: `{process_summary.get('active_run_count', 0)}`.",
        f"- Managed active runs: `{process_summary.get('managed_active_run_count', 0)}`.",
        f"- Untracked active Codex/Claude processes: `{process_summary.get('untracked_active_process_count', 0)}`.",
        f"- Queued issues: `{process_summary.get('queued_issue_count', 0)}`.",
        f"- Blocked issues: `{process_summary.get('blocked_issue_count', 0)}`.",
        "",
    ]
    for benefit in process_summary.get("benefits") or []:
        lines.append(f"- {benefit}")
    lines.extend(["", f"## Candidate Chores (`{scope}`)", ""])
    if not candidates:
        lines.append("- No candidate chores found.")
    else:
        for item in candidates:
            status = "existing" if item.get("existing_issue_id") else "new"
            lines.append(f"- `{item['fingerprint']}` {item['title']} ({status})")
            if item.get("owned_paths"):
                lines.append(f"  Owned paths: `{', '.join(item['owned_paths'])}`")
    lines.extend(["", "## Created This Run", ""])
    if not created:
        lines.append("- None.")
    else:
        for item in created:
            issue_id = item.get("issue_id") or item.get("id") or "unknown"
            lines.append(f"- `#{issue_id}` {item.get('title') or item.get('subject') or ''}")
    lines.extend(["", "## Dispatch", ""])
    if dispatch_summary:
        lines.append(f"- Status: `{dispatch_summary.get('status', 'unknown')}`.")
        if dispatch_summary.get("agent_pool"):
            pool = dispatch_summary["agent_pool"]
            lines.append(f"- Pool return code: `{pool.get('returncode')}`.")
            if pool.get("payload", {}).get("reason_summary"):
                reason = pool["payload"]["reason_summary"]
                lines.append(f"- Pool reason: `{reason.get('primary_reason', 'unknown')}`.")
    else:
        lines.append("- Not run.")
    return "\n".join(lines) + "\n"


def mirror_latest(run_dir: Path) -> None:
    latest = RUN_ROOT / "latest"
    if latest.exists() or latest.is_symlink():
        if latest.is_dir() and not latest.is_symlink():
            shutil.rmtree(latest)
        else:
            latest.unlink()
    shutil.copytree(run_dir, latest)


def resolve_run_dir(value: str = "", *, create: bool) -> Path:
    run_dir = Path(value) if value else RUN_ROOT / run_id()
    if not run_dir.is_absolute():
        run_dir = ROOT / run_dir
    if create:
        run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def write_run_artifacts(
    *,
    run_dir: Path,
    generated_at: str,
    scope: str,
    candidates: list[dict[str, Any]],
    created: list[dict[str, Any]],
    dispatch_summary: dict[str, Any],
    process_summary: dict[str, Any],
) -> dict[str, Any]:
    markdown = render_markdown(
        generated_at=generated_at,
        scope=scope,
        candidates=candidates,
        created=created,
        dispatch_summary=dispatch_summary,
        process_summary=process_summary,
    )
    paths = {
        "candidate_chores": run_dir / "candidate_chores.json",
        "created_issues": run_dir / "created_issues.json",
        "dispatch_summary": run_dir / "dispatch_summary.json",
        "markdown": run_dir / "claude-code-chores.md",
        "status": run_dir / "status.json",
    }
    write_json(paths["candidate_chores"], candidates)
    write_json(paths["created_issues"], created)
    write_json(paths["dispatch_summary"], dispatch_summary)
    paths["markdown"].write_text(markdown, encoding="utf-8")
    status = {
        "generated_at": generated_at,
        "run_dir": rel(run_dir),
        "scope": scope,
        "candidate_count": len(candidates),
        "new_candidate_count": len([item for item in candidates if item.get("eligible_to_create")]),
        "created_count": len(created),
        "dispatch_status": dispatch_summary.get("status", "not_run") if dispatch_summary else "not_run",
        "artifacts": {name: rel(path) for name, path in paths.items() if name != "status"},
        "process_summary": process_summary,
    }
    write_json(paths["status"], status)
    mirror_latest(run_dir)
    return status


def build_story(candidate: dict[str, Any], draft_dir: Path) -> dict[str, Any]:
    validation_path = rel(draft_dir / "validation.json")
    run_dir = "workspace/runs/agent-work/0"
    output_path = f"{run_dir}/worker-handoff.md"
    return {
        "schema_version": "1.0",
        "issue": {"id": 0, "title": candidate["task_title"], "package": DEFAULT_PACKAGE},
        "lane": {"owner": "claude-chores", "node": "linux", "agent": "claude-code", "role": "builder"},
        "paths": {"run_dir": run_dir},
        "scope": {"goal": candidate["description"], "acceptance": candidate["acceptance"]},
        "expected_outputs": [
            {
                "path": output_path,
                "description": "Worker handoff summarizing delivered changes, validation, evidence, and residual risk.",
                "owner": "claude-chores",
                "required": True,
            }
        ],
        "validation": {
            "manifest": validation_path,
            "mode": "no-model",
            "no_model_eligible": True,
            "risk": "medium",
            "escalation_triggers": ["missing_manifest", "failed_deterministic_command", "ambiguity"],
            "commands": candidate["validation_commands"],
        },
        "deliverables": {
            "manifest": f"{run_dir}/deliverables.json",
            "hub": f"{run_dir}/start-here.html",
        },
        "review_gate": {
            "required_sections": ["Delivered", "Validation", "Evidence", "Residual risk"],
            "residual_risk_required": True,
        },
        "metadata": {
            "drafted_at": now_iso(),
            "source": "claude-chores",
            "fingerprint": candidate["fingerprint"],
            "owned_paths": candidate["owned_paths"],
        },
    }


def build_validation(story: dict[str, Any], story_path: Path, candidate: dict[str, Any]) -> dict[str, Any]:
    checks = [
        {
            "name": "worker-handoff-exists",
            "type": "file_exists",
            "path": "workspace/runs/agent-work/{issue}/worker-handoff.md",
            "required": True,
        }
    ]
    checks.extend(
        {
            "name": f"command-{index}",
            "type": "command",
            "command": command,
            "cwd": ".",
            "timeout_seconds": 60,
            "expect_exit": 0,
            "required": True,
        }
        for index, command in enumerate(candidate.get("validation_commands") or [], start=1)
    )
    return {
        "schema": "cento.validation-manifest.v1",
        "task": str(story["issue"]["title"]),
        "story_manifest": rel(story_path),
        "claim": str(story["scope"]["goal"]),
        "risk": "medium",
        "decision_requested": "approve",
        "checks": checks,
        "manual_review": [],
        "coverage": {
            "deterministic_checks": len(checks),
            "manual_review_items": 0,
            "automation_coverage_percent": 100.0,
        },
        "stats_policy": {
            "ai_calls_used": 0,
            "estimated_ai_cost": 0,
            "requires_total_duration_ms": True,
            "requires_per_check_duration_ms": True,
        },
        "created_at": now_iso(),
    }


def update_canonical_validation(issue_id: int, candidate: dict[str, Any], source_story: dict[str, Any]) -> dict[str, str]:
    story_path = ROOT / "workspace" / "runs" / "agent-work" / str(issue_id) / "story.json"
    validation_path = story_path.with_name("validation.json")
    story = read_json(story_path) or source_story
    story.setdefault("issue", {})["id"] = issue_id
    story["issue"]["title"] = candidate["task_title"]
    story["issue"]["package"] = DEFAULT_PACKAGE
    story.setdefault("paths", {})["run_dir"] = rel(story_path.parent)
    story.setdefault("validation", {})["manifest"] = rel(validation_path)
    story.setdefault("deliverables", {})["manifest"] = rel(story_path.parent / "deliverables.json")
    story.setdefault("deliverables", {})["hub"] = rel(story_path.parent / "start-here.html")
    expected_outputs = story.get("expected_outputs") if isinstance(story.get("expected_outputs"), list) else []
    for item in expected_outputs:
        if isinstance(item, dict) and str(item.get("path") or "").endswith("worker-handoff.md"):
            item["path"] = rel(story_path.parent / "worker-handoff.md")
    story_path.parent.mkdir(parents=True, exist_ok=True)
    story_path.write_text(json.dumps(story, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    validation = build_validation(story, story_path, candidate)
    validation["story_manifest"] = rel(story_path)
    for check in validation["checks"]:
        if isinstance(check, dict) and str(check.get("path") or "").endswith("worker-handoff.md"):
            check["path"] = rel(story_path.parent / "worker-handoff.md")
    write_json(validation_path, validation)
    return {"story_manifest": rel(story_path), "validation_manifest": rel(validation_path)}


def create_agent_work_issue(candidate: dict[str, Any], run_dir: Path, *, dry_run: bool) -> dict[str, Any]:
    draft_dir = run_dir / "drafts" / candidate["fingerprint"]
    draft_dir.mkdir(parents=True, exist_ok=True)
    story_path = draft_dir / "story.json"
    validation_path = draft_dir / "validation.json"
    story = build_story(candidate, draft_dir)
    validation = build_validation(story, story_path, candidate)
    write_json(story_path, story)
    write_json(validation_path, validation)
    command = [
        "python3",
        "scripts/agent_work.py",
        "create",
        "--title",
        candidate["task_title"],
        "--manifest",
        rel(story_path),
        "--description",
        candidate["description"],
        "--node",
        candidate["node"],
        "--agent",
        candidate["agent"],
        "--role",
        candidate["role"],
        "--package",
        DEFAULT_PACKAGE,
        "--json",
    ]
    for owned in candidate.get("owned_paths") or []:
        command.extend(["--owns", str(owned)])
    record = {
        "fingerprint": candidate["fingerprint"],
        "title": candidate["task_title"],
        "dry_run": dry_run,
        "draft_story_manifest": rel(story_path),
        "draft_validation_manifest": rel(validation_path),
        "command": shlex.join(command),
    }
    if dry_run:
        record["status"] = "planned"
        return record
    result = run_command(command, timeout=60)
    record.update(command_result_payload(result))
    if result.returncode != 0:
        record["status"] = "failed"
        return record
    try:
        issue = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        issue = {}
    issue_id = int(issue.get("id") or 0)
    record["issue_id"] = issue_id
    record["issue"] = issue
    if issue_id > 0:
        record.update(update_canonical_validation(issue_id, candidate, story))
        record["status"] = "created"
    else:
        record["status"] = "failed"
        record["stderr"] = record.get("stderr") or "agent-work create did not return an issue id"
    return record


def run_pool(args: argparse.Namespace, *, dry_run: bool) -> dict[str, Any]:
    command = [
        "./scripts/cento.sh",
        "agent-pool-kick",
        "--package",
        DEFAULT_PACKAGE,
        "--builder-target",
        str(args.builder_target),
        "--small-target",
        str(args.small_target),
        "--validator-target",
        str(args.validator_target),
        "--coordinator-target",
        str(args.coordinator_target),
        "--max-launch",
        str(args.max_launch),
        "--runtime",
        args.runtime,
        "--model",
        args.model,
    ]
    if dry_run:
        command.append("--dry-run")
    env = os.environ.copy()
    env["CENTO_AGENT_RUNTIME"] = args.runtime
    env["CENTO_POOL_CLAUDE_MODEL"] = args.model
    result = run_command(command, env=env, timeout=120)
    payload: dict[str, Any] = {}
    if result.stdout.strip():
        try:
            parsed = json.loads(result.stdout)
            if isinstance(parsed, dict):
                payload = parsed
        except json.JSONDecodeError:
            payload = {}
    return {
        "status": "dry_run" if dry_run else ("completed" if result.returncode == 0 else "failed"),
        "command": shlex.join(command),
        "agent_pool": {**command_result_payload(result), "payload": payload},
    }


def command_plan(args: argparse.Namespace) -> int:
    generated_at = now_iso()
    run_dir = resolve_run_dir(args.run_dir, create=True)
    issues = agent_work_issues()
    active_runs = agent_work_active_runs(include_untracked=True)
    candidates = annotate_existing(discover_candidate_chores(args.scope, issues), issues)
    process_summary = process_benefit_summary(active_runs, issues)
    status = write_run_artifacts(
        run_dir=run_dir,
        generated_at=generated_at,
        scope=args.scope,
        candidates=candidates,
        created=[],
        dispatch_summary={},
        process_summary=process_summary,
    )
    print(json.dumps(status, indent=2, sort_keys=True) if args.json else f"planned {rel(run_dir)}")
    return 0


def command_run(args: argparse.Namespace) -> int:
    generated_at = now_iso()
    run_dir = resolve_run_dir(args.run_dir, create=True)
    issues = agent_work_issues()
    active_runs = agent_work_active_runs(include_untracked=True)
    candidates = annotate_existing(discover_candidate_chores(args.scope, issues), issues)
    eligible = [item for item in candidates if item.get("eligible_to_create")][: max(0, args.chore_limit)]
    created = [create_agent_work_issue(item, run_dir, dry_run=args.dry_run) for item in eligible]
    dispatch_summary = run_pool(args, dry_run=args.dry_run)
    process_summary = process_benefit_summary(active_runs, issues)
    status = write_run_artifacts(
        run_dir=run_dir,
        generated_at=generated_at,
        scope=args.scope,
        candidates=candidates,
        created=created,
        dispatch_summary=dispatch_summary,
        process_summary=process_summary,
    )
    print(json.dumps(status, indent=2, sort_keys=True) if args.json else f"{status['dispatch_status']} {rel(run_dir)}")
    create_failures = [item for item in created if item.get("status") == "failed"]
    if create_failures:
        return 1
    if not args.dry_run and dispatch_summary.get("status") == "failed":
        return 1
    return 0


def read_crontab(crontab_file: str = "") -> str:
    if crontab_file:
        try:
            return Path(crontab_file).read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""
    result = subprocess.run(["crontab", "-l"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return result.stdout if result.returncode == 0 else ""


def write_crontab(text: str, crontab_file: str = "") -> None:
    if crontab_file:
        path = Path(crontab_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return
    result = subprocess.run(["crontab", "-"], input=text, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "crontab install failed")


def strip_cron_block(text: str) -> str:
    if CRON_BEGIN not in text:
        return text.rstrip() + ("\n" if text.strip() else "")
    before, rest = text.split(CRON_BEGIN, 1)
    if CRON_END not in rest:
        return before.rstrip() + ("\n" if before.strip() else "")
    _old, after = rest.split(CRON_END, 1)
    combined = (before + after).strip()
    return combined + ("\n" if combined else "")


def cron_block(args: argparse.Namespace) -> str:
    interval = int(args.interval_minutes)
    if interval <= 0 or interval > 59:
        raise ValueError("--interval-minutes must be between 1 and 59 for cron step syntax")
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    log_path = STATE_DIR / "claude-chores.log"
    lock_path = STATE_DIR / "claude-chores.lock"
    inner = (
        f"cd {shlex.quote(str(ROOT))} && "
        f"./scripts/cento.sh claude-chores run --scope {shlex.quote(args.scope)} "
        f"--chore-limit {int(args.chore_limit)} --max-launch {int(args.max_launch)} "
        f"--builder-target {int(args.builder_target)} --small-target {int(args.small_target)} "
        f"--validator-target {int(args.validator_target)} --coordinator-target {int(args.coordinator_target)} "
        f"--runtime {shlex.quote(args.runtime)} --model {shlex.quote(args.model)} --scheduler-trigger cron --json"
    )
    command = (
        f"mkdir -p {shlex.quote(str(STATE_DIR))} && "
        f"flock -n {shlex.quote(str(lock_path))} bash -lc {shlex.quote(inner)} "
        f">> {shlex.quote(str(log_path))} 2>&1"
    )
    return "\n".join([CRON_BEGIN, f"*/{interval} * * * * {command}", CRON_END, ""])


def command_install_cron(args: argparse.Namespace) -> int:
    try:
        block = cron_block(args)
    except ValueError as exc:
        print(f"claude-chores install-cron: {exc}", file=sys.stderr)
        return 2
    current = read_crontab(args.crontab_file)
    updated = strip_cron_block(current)
    if updated.strip():
        updated = updated.rstrip() + "\n"
    updated += block
    if not args.dry_run:
        write_crontab(updated, args.crontab_file)
    payload = {
        "status": "planned" if args.dry_run else "installed",
        "cron_installed": not args.dry_run,
        "cron_block": block,
        "crontab_file": args.crontab_file,
        "dry_run": bool(args.dry_run),
    }
    print(json.dumps(payload, indent=2, sort_keys=True) if args.json else payload["status"])
    return 0


def command_uninstall_cron(args: argparse.Namespace) -> int:
    current = read_crontab(args.crontab_file)
    updated = strip_cron_block(current)
    if not args.dry_run:
        write_crontab(updated, args.crontab_file)
    payload = {
        "status": "planned" if args.dry_run else "uninstalled",
        "cron_installed_before": CRON_BEGIN in current and CRON_END in current,
        "crontab_file": args.crontab_file,
        "dry_run": bool(args.dry_run),
    }
    print(json.dumps(payload, indent=2, sort_keys=True) if args.json else payload["status"])
    return 0


def command_status(args: argparse.Namespace) -> int:
    latest_status = read_json(RUN_ROOT / "latest" / "status.json")
    crontab_text = read_crontab(args.crontab_file)
    cron_installed = CRON_BEGIN in crontab_text and CRON_END in crontab_text
    active_runs = agent_work_active_runs(include_untracked=True)
    issues = agent_work_issues()
    payload = {
        "status": latest_status.get("dispatch_status", "unknown") if latest_status else "unknown",
        "latest_run_dir": latest_status.get("run_dir", "") if latest_status else "",
        "latest_status": latest_status,
        "cron_installed": cron_installed,
        "cron_block": cron_block(args) if cron_installed else "",
        "process_summary": process_benefit_summary(active_runs, issues),
        "agent_pool_latest": read_json(STATE_DIR / "agent-pool-kick-latest.json"),
        "crontab_file": args.crontab_file,
    }
    print(json.dumps(payload, indent=2, sort_keys=True) if args.json else f"{payload['status']} cron={payload['cron_installed']}")
    return 0


def add_common_run_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--scope", choices=["broad-repo"], default="broad-repo")
    parser.add_argument("--run-dir", default="")
    parser.add_argument("--json", action="store_true")


def add_pool_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--chore-limit", type=int, default=2)
    parser.add_argument("--max-launch", type=int, default=2)
    parser.add_argument("--builder-target", type=int, default=DEFAULT_ACTIVE_TARGETS["builder"])
    parser.add_argument("--small-target", type=int, default=DEFAULT_ACTIVE_TARGETS["small"])
    parser.add_argument("--validator-target", type=int, default=DEFAULT_ACTIVE_TARGETS["validator"])
    parser.add_argument("--coordinator-target", type=int, default=DEFAULT_ACTIVE_TARGETS["coordinator"])
    parser.add_argument("--runtime", default=DEFAULT_RUNTIME)
    parser.add_argument("--model", default=DEFAULT_MODEL)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create and launch bounded Claude Code chores for Cento maintenance.")
    sub = parser.add_subparsers(dest="command", required=True)

    plan = sub.add_parser("plan", help="Discover candidate Claude chores and write run artifacts without creating tasks.")
    add_common_run_flags(plan)
    plan.set_defaults(func=command_plan)

    run = sub.add_parser("run", help="Create bounded Claude chores and kick the Claude-only worker pool.")
    add_common_run_flags(run)
    add_pool_flags(run)
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--scheduler-trigger", default="")
    run.set_defaults(func=command_run)

    status = sub.add_parser("status", help="Show latest chore run, cron, active process, and pool status.")
    add_pool_flags(status)
    status.add_argument("--scope", choices=["broad-repo"], default="broad-repo")
    status.add_argument("--interval-minutes", type=int, default=30)
    status.add_argument("--crontab-file", default=os.environ.get("CENTO_CLAUDE_CHORES_CRONTAB_PATH", ""))
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=command_status)

    install = sub.add_parser("install-cron", help="Install the managed Claude chores cron block.")
    add_pool_flags(install)
    install.add_argument("--scope", choices=["broad-repo"], default="broad-repo")
    install.add_argument("--interval-minutes", type=int, default=30)
    install.add_argument("--crontab-file", default=os.environ.get("CENTO_CLAUDE_CHORES_CRONTAB_PATH", ""))
    install.add_argument("--dry-run", action="store_true")
    install.add_argument("--json", action="store_true")
    install.set_defaults(func=command_install_cron)

    uninstall = sub.add_parser("uninstall-cron", help="Remove the managed Claude chores cron block.")
    uninstall.add_argument("--crontab-file", default=os.environ.get("CENTO_CLAUDE_CHORES_CRONTAB_PATH", ""))
    uninstall.add_argument("--dry-run", action="store_true")
    uninstall.add_argument("--json", action="store_true")
    uninstall.set_defaults(func=command_uninstall_cron)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except RuntimeError as exc:
        print(f"claude-chores: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
