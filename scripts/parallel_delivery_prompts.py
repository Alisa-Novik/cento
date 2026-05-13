#!/usr/bin/env python3
"""Patch Swarm ChatGPT Pro prompt bundle generator.

This helper turns Patch Swarm planning artifacts into local Markdown prompts.
It does not call ChatGPT Pro, OpenAI APIs, Codex, MCP, Taskstream, Redmine, or
worker pools. The operator copy/paste flow is the product boundary.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import parallel_delivery_artifacts as artifact_schema
except ImportError:  # pragma: no cover - fallback for unusual cwd
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import parallel_delivery_artifacts as artifact_schema


ROOT = Path(__file__).resolve().parents[1]
RUNS_ROOT = ROOT / "workspace" / "runs" / "parallel-delivery"
DEFAULT_RUN_DIR = RUNS_ROOT / "proreq-fixture"
DEFAULT_TEMP_ROOT = ROOT / "workspace" / "runs" / "temp" / "chatgpt-pro"
TEMP_COMMAND_DIR = ROOT / "workspace" / "runs" / "temp" / "commands"
DEFAULT_TEMP_COMMAND_ID = "cento-dev-scale-pro-prompt"

CURRENT_SCHEMA_VERSION = 1
DEFAULT_PROMPT_COUNT = 20
MAX_PROMPT_COUNT = 20
PRODUCER = "cento.parallel-delivery.prompts"
FIXTURE_TASK_COUNT = 20

PROMPT_TYPES = {
    "master",
    "lane",
    "task-cluster",
    "validation",
    "integration",
    "evidence",
    "human-handoff",
}

LANES = {
    "all",
    "builder",
    "validator",
    "docs-evidence",
    "coordinator",
    "integrator",
    "human-handoff",
}

LANE_ORDER = [
    "coordinator",
    "builder",
    "validator",
    "docs-evidence",
    "integrator",
    "human-handoff",
]

REQUIRED_PROMPT_SECTIONS = [
    "## Mission",
    "## Task Scope",
    "## Owned Paths",
    "## Read-Only Context",
    "## Acceptance Criteria",
    "## Validation Plan",
    "## Evidence To Write",
    "## Safety Rules",
    "## Codex Output Format",
    "## Expected Response Shape",
]

CODEX_OUTPUT_SCHEMA = [
    "1. CODEx_THREAD_TITLE",
    "2. MISSION",
    "3. DISCOVERY_COMMANDS",
    "4. OWNED_PATHS_CANDIDATES",
    "5. IMPLEMENTATION_PLAN",
    "6. CODE_DESIGN",
    "7. VALIDATION_PLAN",
    "8. EVIDENCE_TO_WRITE",
    "9. ACCEPTANCE_CRITERIA",
    "10. RISKS_AND_GUARDS",
    "11. PASTE_TO_CODEX",
]

RUN_LEVEL_PROMPTS = [
    ("validation", "Validation Strategy Prompt", "validation-strategy"),
    ("integration", "Safe Integration Review Prompt", "integration-readiness"),
    ("evidence", "Docs And Evidence Package Prompt", "evidence-package"),
    ("validation", "Path Lease Review Prompt", "path-lease-review"),
    ("human-handoff", "Failure Handling Prompt", "failure-handling"),
    ("evidence", "Operator Demo Plan Prompt", "operator-demo"),
    ("validation", "Safety And Secret Review Prompt", "safety-review"),
    ("integration", "Acceptance Contract Review Prompt", "acceptance-review"),
    ("evidence", "Codex Handoff Packet Prompt", "codex-handoff"),
]

SECRET_PATH_PARTS = {
    ".env",
    ".env.mcp",
    "secret",
    "secrets",
    "credential",
    "credentials",
    "token",
    "tokens",
    "key",
    "keys",
}

SECRET_VALUE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"sk-[A-Za-z0-9_-]{16,}"), "openai-like key"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"), "github-like token"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "aws access key"),
    (re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----"), "private key"),
    (
        re.compile(
            r"(?i)\b(password|passwd|token|secret|api[_-]?key)\s*[:=]\s*['\"]?([A-Za-z0-9_./+=-]{8,})"
        ),
        "secret assignment",
    ),
]


class PromptBundleError(Exception):
    """Raised when prompt bundle generation or validation fails."""


@dataclass(frozen=True)
class PromptBundleRequest:
    run_id: str
    run_dir: Path
    count: int
    lane: str
    split_plan_path: Path | None = None
    task_graph_path: Path | None = None
    path_leases_path: Path | None = None
    request_file: Path | None = None
    out_dir: Path | None = None
    temp_dir: Path | None = None
    copy_to_temp: bool = False
    fixed_timestamp: str | None = None


@dataclass(frozen=True)
class PromptSpec:
    prompt_id: str
    prompt_type: str
    title: str
    lane: str
    task_ids: list[str]
    owned_paths: list[str]
    read_only_paths: list[str]
    validation_commands: list[str]
    evidence_requirements: list[str]
    copy_order: int
    slug: str


@dataclass(frozen=True)
class PromptBundleResult:
    run_id: str
    run_dir: Path
    prompt_count: int
    prompt_index_path: Path
    prompt_bundle_path: Path
    prompts: list[dict[str, Any]]
    temp_bridge_path: Path | None
    warnings: list[str]
    errors: list[str]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stable_json_dumps(payload: dict[str, Any]) -> str:
    """Return deterministic JSON with sorted keys, two-space indent, and trailing newline."""
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write deterministic JSON artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json_dumps(payload), encoding="utf-8")


def sha256_text(text: str) -> str:
    """Return sha256 digest for prompt index validation."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    """Return sha256 digest for file references."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def resolve_path(value: str | Path | None, *, default: Path | None = None) -> Path | None:
    if value is None or str(value) == "":
        return default
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def path_for_index(run_dir: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(run_dir.resolve()).as_posix()
    except ValueError:
        return rel(path)


def resolve_index_entry_path(run_dir: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    run_relative = run_dir / path
    if run_relative.exists():
        return run_relative
    root_relative = ROOT / path
    if root_relative.exists():
        return root_relative
    return run_relative


def temp_command_dir() -> Path:
    value = os.environ.get("CENTO_TEMP_COMMAND_DIR", "")
    if value:
        path = Path(value)
        return path if path.is_absolute() else ROOT / path
    return TEMP_COMMAND_DIR


def validate_prompt_count(count: int) -> int:
    """Require 1 <= count <= 20; docs recommend 15 or 20."""
    if not 1 <= int(count) <= MAX_PROMPT_COUNT:
        raise PromptBundleError("count must be between 1 and 20")
    return int(count)


def normalize_lane(lane: str | None) -> str:
    """Normalize lane filter and reject unknown lanes."""
    value = (lane or "all").strip().lower()
    if value not in LANES:
        raise PromptBundleError(f"lane must be one of {', '.join(sorted(LANES))}")
    return value


def _looks_like_secret_path(path: Path) -> bool:
    lowered = [part.lower() for part in path.parts]
    return any(part in SECRET_PATH_PARTS or part.startswith(".env") for part in lowered)


def safe_read_text(path: Path, *, max_chars: int = 20000) -> str:
    """Read tracked/safe artifact text with bounded size; do not read local secret files."""
    if _looks_like_secret_path(path):
        raise PromptBundleError("refusing to read local secret-like path")
    return path.read_text(encoding="utf-8", errors="replace")[:max_chars]


def redact_secret_like_text(text: str) -> tuple[str, list[str]]:
    """Redact secret-like strings from request/context before prompt rendering."""
    warnings: list[str] = []
    redacted = text
    for pattern, label in SECRET_VALUE_PATTERNS:
        if pattern.search(redacted):
            warnings.append(f"redacted {label}")
            if label == "secret assignment":
                redacted = pattern.sub(lambda match: f"{match.group(1)}=[REDACTED_SECRET]", redacted)
            else:
                redacted = pattern.sub("[REDACTED_SECRET]", redacted)
    return redacted, sorted(set(warnings))


def read_json_artifact(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        raise PromptBundleError(f"{rel(path)} invalid JSON: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise PromptBundleError(f"{rel(path)} must be a JSON object")
    return payload


def _metadata_comment(artifact_type: str, run_id: str, timestamp: str) -> str:
    payload = {
        "artifact_type": artifact_type,
        "created_at": timestamp,
        "run_id": run_id,
        "schema_version": CURRENT_SCHEMA_VERSION,
    }
    return f"<!-- cento-artifact: {json.dumps(payload, sort_keys=True, separators=(',', ':'))} -->"


def _common(artifact_type: str, run_id: str, timestamp: str, command: str) -> dict[str, Any]:
    return {
        "artifact_type": artifact_type,
        "created_at": timestamp,
        "evidence_pointers": [],
        "provenance": {
            "command": command,
            "notes": [],
            "producer": PRODUCER,
            "repo": "cento",
            "source": "fixture",
        },
        "run_id": run_id,
        "schema_version": CURRENT_SCHEMA_VERSION,
    }


def _fixture_task(index: int, run_id: str, timestamp: str) -> dict[str, Any]:
    lane = LANE_ORDER[(index - 1) % len(LANE_ORDER)]
    task_id = f"task-{index:04d}"
    profile_by_lane = {
        "builder": "python-builder",
        "validator": "test-writer",
        "docs-evidence": "docs-evidence-writer",
        "coordinator": "factory-planner",
        "integrator": "safe-integrator",
        "human-handoff": "human-operator",
    }
    risk = "human" if lane == "human-handoff" else ("high" if lane == "integrator" else ("medium" if lane in {"builder", "coordinator"} else "low"))
    artifact_base = f"workspace/runs/parallel-delivery/{run_id}"
    owned = [f"{artifact_base}/task-work/{task_id}/"]
    if lane == "human-handoff":
        owned = [f"{artifact_base}/human-handoff/{task_id}.md"]
    depends_on = [f"task-{index - 1:04d}"] if lane == "integrator" and index > 1 else []
    return {
        "acceptance_contract": [
            "Required artifacts are written only under owned paths.",
            "Validation commands complete or exact failure evidence is recorded.",
            "No unrelated dirty work, local secret files, or external task systems are touched.",
        ],
        "dependencies": depends_on,
        "evidence_pointers": [],
        "expected_artifacts": [f"task-work/{task_id}/evidence.json", f"task-contracts/{task_id}.md"],
        "human_handoff": lane == "human-handoff",
        "integration_notes": ["Safe Integrator or operator review decides any later apply order."],
        "lane": lane,
        "owned_paths": owned,
        "read_only_paths": [
            "docs/patch-swarm.md",
            "docs/parallel-delivery/patch-swarm-artifacts.md",
            "docs/parallel-delivery/patch-swarm-planner.md",
        ],
        "rejection_triggers": [
            "Touches an unowned path.",
            "Drops acceptance, validation, or evidence requirements.",
            "Requires live services or copies local secret values.",
        ],
        "risk_tier": risk,
        "state": "leased",
        "story": f"As a Cento operator, I need bounded {lane} work for {task_id} with copy/paste prompt evidence.",
        "summary": f"Produce deterministic {lane} evidence for {task_id}.",
        "task_id": task_id,
        "title": f"ProReq prompt fixture {task_id} {lane}",
        "validation_commands": [
            f"test -f {artifact_base}/prompts/prompt-0001-master.md",
            f"python3 -m json.tool {artifact_base}/prompt-index.json >/dev/null",
        ],
        "worker_profile": profile_by_lane[lane],
        "written_at": timestamp,
    }


def write_fixture_inputs(run_dir: Path, *, run_id: str, timestamp: str, task_count: int = FIXTURE_TASK_COUNT) -> None:
    """Write deterministic request, split-plan, task-graph, and path-leases inputs."""
    run_dir.mkdir(parents=True, exist_ok=True)
    request_body = "\n".join(
        [
            _metadata_comment("request", run_id, timestamp),
            "# Patch Swarm ProReq Prompt Fixture",
            "",
            "Create a local-only ChatGPT Pro prompt bundle for Patch Swarm workers.",
            "The fixture must prove prompt counts, lane filtering, validation sections, evidence, and temp mirror behavior.",
            "",
        ]
    )
    (run_dir / "request.md").write_text(request_body, encoding="utf-8")

    tasks = [_fixture_task(index, run_id, timestamp) for index in range(1, task_count + 1)]
    split_plan = {
        **_common("split-plan", run_id, timestamp, "patch-swarm prompts write-fixture"),
        "candidate_count": len(tasks),
        "candidate_target": task_count,
        "lanes": sorted(LANES - {"all"}),
        "max_candidate_tasks": task_count,
        "max_parallel_agents": 5,
        "planner_mode": "fixture",
        "planning_policy": {
            "avoid_overlapping_owned_paths": True,
            "coarse_lanes_first": True,
            "prompt_count_is_not_task_count": True,
        },
        "request": {
            "request_file": "request.md",
            "summary": "Create a local-only ChatGPT Pro prompt bundle for Patch Swarm workers.",
            "title": "Patch Swarm ProReq Prompt Fixture",
        },
        "tasks": tasks,
        "updated_at": timestamp,
    }
    write_json(run_dir / "split-plan.json", split_plan)

    task_ids = [task["task_id"] for task in tasks]
    edges = [
        {"from": dep, "reason": f"{task['task_id']} consumes {dep} output", "to": task["task_id"], "type": "depends_on"}
        for task in tasks
        for dep in task["dependencies"]
    ]
    groups = []
    for offset in range(0, len(task_ids), 5):
        groups.append({"automated": True, "group_id": f"group-{len(groups) + 1:04d}", "task_ids": task_ids[offset : offset + 5]})
    task_graph = {
        **_common("task-graph", run_id, timestamp, "patch-swarm prompts write-fixture"),
        "edges": edges,
        "max_parallel_agents": 5,
        "nodes": [
            {
                "human_handoff": task["human_handoff"],
                "lane": task["lane"],
                "owned_paths": task["owned_paths"],
                "risk_tier": task["risk_tier"],
                "task_id": task["task_id"],
            }
            for task in tasks
        ],
        "parallel_groups": groups,
        "topological_order": task_ids,
        "updated_at": timestamp,
    }
    write_json(run_dir / "task-graph.json", task_graph)

    leases = {
        **_common("path-leases", run_id, timestamp, "patch-swarm prompts write-fixture"),
        "conflicts": [],
        "leases": [
            {
                "created_at": timestamp,
                "lease_id": f"lease-{task['task_id']}",
                "owned_paths": task["owned_paths"],
                "read_only_paths": task["read_only_paths"],
                "state": "active",
                "task_id": task["task_id"],
            }
            for task in tasks
        ],
    }
    write_json(run_dir / "path-leases.json", leases)


def _source_path(run_dir: Path, explicit: Path | None, filename: str) -> Path:
    return explicit if explicit is not None else run_dir / filename


def load_run_context(request: PromptBundleRequest) -> dict[str, Any]:
    """Load request, split plan, task graph, path leases, and derive task context."""
    split_path = _source_path(request.run_dir, request.split_plan_path, "split-plan.json")
    graph_path = _source_path(request.run_dir, request.task_graph_path, "task-graph.json")
    leases_path = _source_path(request.run_dir, request.path_leases_path, "path-leases.json")
    request_path = _source_path(request.run_dir, request.request_file, "request.md")
    split_plan = read_json_artifact(split_path)
    task_graph = read_json_artifact(graph_path)
    path_leases = read_json_artifact(leases_path)
    request_text = safe_read_text(request_path) if request_path.exists() else ""
    request_text, redaction_warnings = redact_secret_like_text(request_text)
    task_rows = [item for item in split_plan.get("tasks", []) if isinstance(item, dict)]
    tasks_by_id = {str(task.get("task_id") or ""): task for task in task_rows if task.get("task_id")}
    leases_by_task: dict[str, dict[str, Any]] = {}
    for lease in path_leases.get("leases", []):
        if isinstance(lease, dict) and lease.get("task_id"):
            leases_by_task[str(lease["task_id"])] = lease
    order = [str(item) for item in task_graph.get("topological_order", []) if str(item) in tasks_by_id]
    for task_id in tasks_by_id:
        if task_id not in order:
            order.append(task_id)
    return {
        "run_id": request.run_id,
        "run_dir": request.run_dir,
        "request_text": request_text,
        "redaction_warnings": redaction_warnings,
        "split_plan": split_plan,
        "task_graph": task_graph,
        "path_leases": path_leases,
        "tasks": [tasks_by_id[task_id] for task_id in order],
        "tasks_by_id": tasks_by_id,
        "leases_by_task": leases_by_task,
        "source_paths": {
            "request": request_path,
            "split_plan": split_path,
            "task_graph": graph_path,
            "path_leases": leases_path,
        },
    }


def _task_value(task: dict[str, Any], key: str) -> list[str]:
    value = task.get(key)
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return []


def _unique(items: list[str], *, limit: int = 80) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
        if len(result) >= limit:
            break
    return result


def _task_ids_for_lane(context: dict[str, Any], lane: str) -> list[str]:
    return [
        str(task.get("task_id"))
        for task in context["tasks"]
        if str(task.get("task_id") or "") and (lane == "all" or str(task.get("lane") or "") == lane)
    ]


def _paths_for_tasks(context: dict[str, Any], task_ids: list[str], field: str) -> list[str]:
    tasks_by_id = context["tasks_by_id"]
    leases_by_task = context["leases_by_task"]
    values: list[str] = []
    for task_id in task_ids:
        lease = leases_by_task.get(task_id, {})
        values.extend([str(item) for item in lease.get(field, [])] if isinstance(lease.get(field), list) else [])
        values.extend(_task_value(tasks_by_id.get(task_id, {}), field))
    return _unique(values, limit=60)


def _validation_for_tasks(context: dict[str, Any], task_ids: list[str]) -> list[str]:
    tasks_by_id = context["tasks_by_id"]
    commands: list[str] = []
    for task_id in task_ids:
        commands.extend(_task_value(tasks_by_id.get(task_id, {}), "validation_commands"))
    if not commands:
        commands = [
            "python3 scripts/parallel_delivery_prompts.py validate-bundle --run-dir workspace/runs/parallel-delivery/proreq-fixture --json",
            "python3 -m json.tool workspace/runs/parallel-delivery/proreq-fixture/prompt-index.json >/dev/null",
        ]
    return _unique(commands, limit=20)


def _evidence_for_tasks(context: dict[str, Any], task_ids: list[str]) -> list[str]:
    tasks_by_id = context["tasks_by_id"]
    evidence: list[str] = []
    for task_id in task_ids:
        evidence.extend(_task_value(tasks_by_id.get(task_id, {}), "expected_artifacts"))
    evidence.extend(["prompt-validation.json", "prompt-validation-report.md", "summary.md"])
    return _unique(evidence, limit=30)


def _acceptance_for_tasks(context: dict[str, Any], task_ids: list[str]) -> list[str]:
    tasks_by_id = context["tasks_by_id"]
    acceptance: list[str] = []
    for task_id in task_ids:
        acceptance.extend(_task_value(tasks_by_id.get(task_id, {}), "acceptance_contract"))
    if not acceptance:
        acceptance = [
            "Generated Codex packet preserves owned path boundaries.",
            "Validation and evidence requirements are explicit.",
            "No live services or secret material are required.",
        ]
    return _unique(acceptance, limit=30)


def _spec(
    context: dict[str, Any],
    *,
    copy_order: int,
    prompt_type: str,
    title: str,
    lane: str,
    task_ids: list[str],
    slug: str,
) -> PromptSpec:
    if prompt_type not in PROMPT_TYPES:
        raise PromptBundleError(f"unknown prompt_type: {prompt_type}")
    if lane != "all" and lane not in LANES:
        raise PromptBundleError(f"unknown lane: {lane}")
    task_ids = _unique(task_ids, limit=80)
    if not task_ids:
        task_ids = _task_ids_for_lane(context, lane if lane != "all" else "all")
    owned_paths = _paths_for_tasks(context, task_ids, "owned_paths")
    read_only_paths = _paths_for_tasks(context, task_ids, "read_only_paths")
    if not owned_paths:
        owned_paths = [f"workspace/runs/parallel-delivery/{context['run_id']}/prompt-work/{slug}/"]
    if not read_only_paths:
        read_only_paths = ["docs/patch-swarm.md", "scripts/parallel_delivery.py", "data/tools.json"]
    return PromptSpec(
        copy_order=copy_order,
        evidence_requirements=_evidence_for_tasks(context, task_ids),
        lane=lane,
        owned_paths=owned_paths,
        prompt_id=f"prompt-{copy_order:04d}",
        prompt_type=prompt_type,
        read_only_paths=read_only_paths,
        slug=slug,
        task_ids=task_ids,
        title=title,
        validation_commands=_validation_for_tasks(context, task_ids),
    )


def build_prompt_specs(context: dict[str, Any], *, count: int, lane: str) -> list[PromptSpec]:
    """Create deterministic master/lane/task-cluster prompt specs."""
    count = validate_prompt_count(count)
    lane = normalize_lane(lane)
    specs: list[PromptSpec] = []
    all_task_ids = _task_ids_for_lane(context, "all")
    filtered_task_ids = all_task_ids if lane == "all" else _task_ids_for_lane(context, lane)

    specs.append(
        _spec(
            context,
            copy_order=1,
            prompt_type="master",
            title="Master Patch Swarm Implementation Prompt",
            lane="all",
            task_ids=all_task_ids,
            slug="master",
        )
    )
    if count == 1:
        return specs

    lanes = LANE_ORDER if lane == "all" else [lane]
    for lane_name in lanes:
        if len(specs) >= count - 1:
            break
        lane_task_ids = _task_ids_for_lane(context, lane_name)
        specs.append(
            _spec(
                context,
                copy_order=len(specs) + 1,
                prompt_type="human-handoff" if lane_name == "human-handoff" else "lane",
                title=f"{lane_name.title().replace('-', ' ')} Lane Prompt",
                lane=lane_name,
                task_ids=lane_task_ids,
                slug=f"lane-{lane_name}",
            )
        )

    task_index = 0
    while len(specs) < count - 1 and task_index < len(filtered_task_ids):
        group = filtered_task_ids[task_index : task_index + 2]
        task_index += 2
        specs.append(
            _spec(
                context,
                copy_order=len(specs) + 1,
                prompt_type="task-cluster",
                title=f"Task Cluster Prompt {' '.join(group)}",
                lane=lane if lane != "all" else "all",
                task_ids=group,
                slug=f"task-cluster-{len(specs) + 1:04d}",
            )
        )

    run_level_index = 0
    while len(specs) < count - 1:
        prompt_type, title, slug = RUN_LEVEL_PROMPTS[run_level_index % len(RUN_LEVEL_PROMPTS)]
        run_level_index += 1
        specs.append(
            _spec(
                context,
                copy_order=len(specs) + 1,
                prompt_type=prompt_type,
                title=title,
                lane=lane if lane != "all" else "all",
                task_ids=filtered_task_ids or all_task_ids,
                slug=slug,
            )
        )

    specs.append(
        _spec(
            context,
            copy_order=count,
            prompt_type="evidence",
            title="Final Evidence And Codex Handoff Prompt",
            lane=lane if lane != "all" else "all",
            task_ids=filtered_task_ids or all_task_ids,
            slug="evidence",
        )
    )
    return specs[:count]


def codex_output_schema_text() -> str:
    """Return required Codex implementation packet schema text."""
    return "\n".join(CODEX_OUTPUT_SCHEMA)


def safety_rules_text() -> str:
    """Return prompt safety rules without copying local secrets."""
    rules = [
        "Do not ask clarifying questions.",
        "Make reversible assumptions.",
        "Do not tell Codex to edit files before running discovery.",
        "Do not tell Codex to mark Done unless validation passes.",
        "If a target file is dirty, preserve unrelated hunks and make minimal additive changes.",
        "Prefer small composable Python/shell tools over large framework rewrites.",
        "Do not read or copy local secret files.",
        "Do not include environment variables, tokens, keys, credentials, or local secret values.",
        "Do not include raw command output that may contain secrets.",
        "Do not include untracked file contents or broad repo dumps.",
        "Do not call OpenAI, ChatGPT Pro, Codex, MCP, Taskstream, Redmine, or live worker systems.",
        "Do not instruct Codex to mutate Taskstream, Redmine, or story state through direct database writes.",
        "Do not instruct Codex to reset, checkout, clean, stash, or overwrite unrelated work.",
    ]
    return "\n".join(f"- {rule}" for rule in rules)


def _bullet(items: list[str], fallback: str = "None.") -> list[str]:
    return [f"- `{item}`" for item in items] if items else [f"- {fallback}"]


def _plain_bullet(items: list[str], fallback: str = "None.") -> list[str]:
    return [f"- {item}" for item in items] if items else [f"- {fallback}"]


def _request_excerpt(context: dict[str, Any]) -> str:
    text = str(context.get("request_text") or "").strip()
    if not text:
        return "No request text was available beyond structured split-plan artifacts."
    compact = "\n".join(line.rstrip() for line in text.splitlines()[:40]).strip()
    return compact[:4000] if compact else "No request text was available beyond structured split-plan artifacts."


def render_prompt(context: dict[str, Any], spec: PromptSpec) -> str:
    """Render a Patch Swarm prompt."""
    artifact = {
        "artifact_type": "chatgpt-pro-prompt",
        "prompt_id": spec.prompt_id,
        "run_id": context["run_id"],
        "schema_version": CURRENT_SCHEMA_VERSION,
    }
    acceptance = _acceptance_for_tasks(context, spec.task_ids)
    dependencies = []
    for task_id in spec.task_ids:
        task = context["tasks_by_id"].get(task_id, {})
        dependencies.extend(_task_value(task, "dependencies"))
    lines = [
        "# Patch Swarm Prompt",
        "",
        f"<!-- cento-artifact: {json.dumps(artifact, sort_keys=True, separators=(',', ':'))} -->",
        "",
        "You are producing a paste-ready Codex implementation packet. You are not editing the repo directly.",
        "Do not ask Codex to call live AI services, mutate external task systems, copy secrets, or overwrite dirty work.",
        "",
        "## Mission",
        "",
        f"Create a high-quality Codex implementation packet for `{spec.title}` in Patch Swarm run `{context['run_id']}`.",
        "The packet must be local-first, discovery-first, reversible, validation-oriented, and safe to paste into Codex.",
        "",
        "## Run Context",
        "",
        f"- Run ID: `{context['run_id']}`",
        f"- Prompt ID: `{spec.prompt_id}`",
        f"- Prompt type: `{spec.prompt_type}`",
        f"- Lane: `{spec.lane}`",
        "- Recommended model: `ChatGPT Pro`",
        "- Operator action: paste this prompt into ChatGPT Pro, then paste the returned implementation packet into Codex.",
        "",
        "Request excerpt:",
        "",
        "```text",
        _request_excerpt(context),
        "```",
        "",
        "## Task Scope",
        "",
        f"- Title: {spec.title}",
        f"- Task IDs: {', '.join(spec.task_ids) if spec.task_ids else 'run-level prompt'}",
        f"- Copy order: {spec.copy_order}",
        f"- Dependencies: {', '.join(_unique(dependencies, limit=20)) if dependencies else 'none'}",
        "",
        "## Owned Paths",
        "",
        *_bullet(spec.owned_paths),
        "",
        "## Read-Only Context",
        "",
        *_bullet(spec.read_only_paths),
        "",
        "## Acceptance Criteria",
        "",
        *_plain_bullet(acceptance),
        "- The generated Codex packet includes explicit discovery commands before any file edits.",
        "- The generated Codex packet preserves unrelated dirty work and avoids destructive git commands.",
        "- The generated Codex packet includes validation and evidence closeout requirements.",
        "",
        "## Validation Plan",
        "",
        *_bullet(spec.validation_commands),
        "- Codex must record exact failures and next actions if a validation command cannot pass.",
        "",
        "## Evidence To Write",
        "",
        *_bullet(spec.evidence_requirements),
        "- Include durable evidence under the run directory or a task-owned evidence path.",
        "",
        "## Safety Rules",
        "",
        safety_rules_text(),
        "",
        "## Codex Output Format",
        "",
        "Return a paste-ready Codex implementation packet with exactly these top-level sections:",
        "",
        "```text",
        codex_output_schema_text(),
        "```",
        "",
        "The packet must also include these instructions for Codex:",
        "",
        "- Do not ask clarifying questions.",
        "- Make reversible assumptions.",
        "- Do not tell Codex to edit files before running discovery.",
        "- Do not tell Codex to mark Done unless validation passes.",
        "- If a target file is dirty, preserve unrelated hunks and make minimal additive changes.",
        "- Prefer small composable Python/shell tools over large framework rewrites.",
        "",
        "## Expected Response Shape",
        "",
        "Respond with only the Codex implementation packet. Do not include prefaces, explanations, or alternative formats.",
        "The packet should be complete enough for Codex to discover, implement, validate, and write evidence without live service calls.",
        "",
        "## Failure Handling",
        "",
        "If the implementation cannot be completed safely, instruct Codex to stop after discovery or validation and write the exact blocker, affected files, and next action.",
        "",
        "## Paste-To-Codex Instructions",
        "",
        "After ChatGPT Pro returns the packet, paste it into Codex from the Cento repo root and let Codex run discovery before edits.",
        "",
    ]
    return "\n".join(lines)


def _prompt_filename(spec: PromptSpec) -> str:
    suffix = spec.slug
    if spec.prompt_type == "master":
        suffix = "master"
    elif spec.prompt_type == "evidence" and spec.slug == "evidence":
        suffix = "evidence"
    return f"{spec.prompt_id}-{suffix}.md"


def write_prompt_index_md(path: Path, bundle: dict[str, Any]) -> None:
    """Write human-readable prompt index."""
    prompts = bundle.get("prompts") if isinstance(bundle.get("prompts"), list) else []
    lines = [
        "# Patch Swarm ChatGPT Pro Prompt Index",
        "",
        "## How to Use",
        "",
        "Open prompts in copy order. Paste each Markdown prompt into ChatGPT Pro, then paste the returned Codex packet into Codex for implementation or review. This bundle does not call live AI services.",
        "",
        "## Prompt Order",
        "",
    ]
    for item in prompts:
        lines.append(f"{item.get('copy_order')}. `{item.get('path')}` - {item.get('title')} ({item.get('prompt_type')}, lane `{item.get('lane')}`)")
    lines.extend(
        [
            "",
            "## Master Prompt",
            "",
            "- Start with `prompt-0001-master.md` for the overall implementation packet.",
            "",
            "## Lane Prompts",
            "",
            "- Use lane and task-cluster prompts for focused worker packets.",
            "",
            "## Temp Bridge",
            "",
            f"- Temp bridge: `{bundle.get('temp_bridge') or 'not requested'}`",
            "",
            "## Evidence",
            "",
            "- Generated prompts, indexes, validation report, and temp bridge metadata are local run artifacts.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_start_here(run_dir: Path, bundle: dict[str, Any]) -> None:
    lines = [
        "# Patch Swarm ProReq Prompt Bundle",
        "",
        "## What This Is",
        "",
        "A local-only ChatGPT Pro prompt bundle for producing paste-ready Codex implementation packets.",
        "",
        "## Prompt Index",
        "",
        "- `prompt-index.md`",
        "- `prompt-index.json`",
        "- `prompt-bundle.json`",
        "",
        "## First Prompt",
        "",
        "- `prompts/prompt-0001-master.md`",
        "",
        "## Validation",
        "",
        "- `prompt-validation.json`",
        "- `prompt-validation-report.md`",
        "",
        "## Temp Bridge",
        "",
        f"- `{bundle.get('temp_bridge') or 'not requested'}`",
        "",
    ]
    (run_dir / "start-here.md").write_text("\n".join(lines), encoding="utf-8")


def write_temp_bridge(request: PromptBundleRequest, bundle: dict[str, Any]) -> dict[str, Any]:
    """Write temp mirror/current prompt and return temp bridge metadata."""
    run_dir = request.run_dir
    temp_dir = request.temp_dir or DEFAULT_TEMP_ROOT / request.run_id
    prompts = bundle.get("prompts") if isinstance(bundle.get("prompts"), list) else []
    temp_prompt_dir = temp_dir / "prompts"
    temp_prompt_dir.mkdir(parents=True, exist_ok=True)
    for old_prompt in temp_prompt_dir.glob("prompt-*.md"):
        old_prompt.unlink()
    for item in prompts:
        source = resolve_index_entry_path(run_dir, str(item.get("path") or ""))
        if source.exists():
            target = temp_prompt_dir / source.name
            target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    index_source = run_dir / "prompt-index.md"
    if index_source.exists():
        (temp_dir / "prompt-index.md").write_text(index_source.read_text(encoding="utf-8"), encoding="utf-8")
    first_prompt = resolve_index_entry_path(run_dir, str(prompts[0].get("path") or "")) if prompts and isinstance(prompts[0], dict) else run_dir / "prompts" / "prompt-0001-master.md"
    current = temp_dir / "current.md"
    if first_prompt.exists():
        text = first_prompt.read_text(encoding="utf-8")
        current.write_text(text, encoding="utf-8")
        (run_dir / "temp-current-prompt.md").write_text(text, encoding="utf-8")
    command_dir = temp_command_dir()
    command_dir.mkdir(parents=True, exist_ok=True)
    temp_command = {
        "copy_file": rel(current),
        "description": "Default ChatGPT Pro prompt bridge for the latest Patch Swarm prompt bundle.",
        "id": DEFAULT_TEMP_COMMAND_ID,
        "node": "local",
        "title": "Patch Swarm ChatGPT Pro Prompt",
    }
    write_json(command_dir / f"{DEFAULT_TEMP_COMMAND_ID}.json", temp_command)
    bridge = {
        "artifact_type": "temp-bridge",
        "cento_temp_command": "cento temp run",
        "cento_temp_supported": True,
        "created_at": request.fixed_timestamp or utc_now(),
        "current_prompt": rel(current),
        "notes": [
            "Existing temp bridge supports the default copy_file entry via `cento temp run`.",
            "The temp run --file and positional file forms are not part of the discovered temp interface.",
            "Prompt generation did not copy to the OS clipboard.",
        ],
        "run_id": request.run_id,
        "schema_version": CURRENT_SCHEMA_VERSION,
        "source_prompt": "prompts/prompt-0001-master.md",
        "temp_command": rel(command_dir / f"{DEFAULT_TEMP_COMMAND_ID}.json"),
        "temp_dir": rel(temp_dir),
    }
    write_json(run_dir / "temp-bridge.json", bridge)
    return bridge


def _validation_report_md(validation: dict[str, Any]) -> str:
    lines = [
        "# Patch Swarm Prompt Validation Report",
        "",
        "## Summary",
        "",
        f"- Status: `{'passed' if validation.get('ok') else 'failed'}`",
        f"- Run ID: `{validation.get('run_id')}`",
        f"- Prompt count: `{validation.get('prompt_count')}`",
        "",
        "## Errors",
        "",
        *([f"- {item}" for item in validation.get("errors", [])] or ["- None"]),
        "",
        "## Warnings",
        "",
        *([f"- {item}" for item in validation.get("warnings", [])] or ["- None"]),
        "",
        "## Checked Prompts",
        "",
    ]
    for item in validation.get("checked_prompts", []):
        lines.append(f"- `{item.get('path')}`")
    lines.append("")
    return "\n".join(lines)


def write_prompt_bundle(request: PromptBundleRequest) -> PromptBundleResult:
    """Write prompt Markdown files, prompt index, bundle metadata, reports, and optional temp bridge."""
    count = validate_prompt_count(request.count)
    lane = normalize_lane(request.lane)
    run_dir = request.run_dir
    out_dir = request.out_dir or run_dir / "prompts"
    run_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    for old_prompt in out_dir.glob("prompt-*.md"):
        old_prompt.unlink()
    context = load_run_context(request)
    timestamp = request.fixed_timestamp or utc_now()
    specs = build_prompt_specs(context, count=count, lane=lane)
    prompt_entries: list[dict[str, Any]] = []
    warnings = list(context.get("redaction_warnings") or [])
    for spec in specs:
        text = render_prompt(context, spec)
        path = out_dir / _prompt_filename(spec)
        path.write_text(text, encoding="utf-8")
        prompt_entries.append(
            {
                "copy_order": spec.copy_order,
                "evidence_requirements": spec.evidence_requirements,
                "lane": spec.lane,
                "operator_action": "paste_into_chatgpt_pro_then_paste_result_to_codex",
                "owned_paths": spec.owned_paths,
                "path": path_for_index(run_dir, path),
                "prompt_id": spec.prompt_id,
                "prompt_type": spec.prompt_type,
                "read_only_paths": spec.read_only_paths,
                "recommended_model": "ChatGPT Pro",
                "sha256": sha256_text(text),
                "task_ids": spec.task_ids,
                "title": spec.title,
                "validation_commands": spec.validation_commands,
            }
        )

    index = {
        "artifact_type": "prompt-index",
        "created_at": timestamp,
        "prompts": prompt_entries,
        "prompt_count": len(prompt_entries),
        "run_id": request.run_id,
        "schema_version": CURRENT_SCHEMA_VERSION,
        "updated_at": timestamp,
    }
    write_json(run_dir / "prompt-index.json", index)

    bundle = {
        "artifact_type": "prompt-bundle",
        "created_at": timestamp,
        "evidence_pointers": [],
        "lane_filter": None if lane == "all" else lane,
        "policy": {
            "include_acceptance_contract": True,
            "include_codex_output_schema": True,
            "include_evidence": True,
            "include_owned_paths": True,
            "include_safety_rules": True,
            "include_validation": True,
            "no_api_calls_by_default": True,
            "no_secrets": True,
            "operator_copy_paste_flow": True,
        },
        "prompt_count": len(prompt_entries),
        "prompts": prompt_entries,
        "provenance": {
            "command": "patch-swarm prompts",
            "notes": [],
            "producer": PRODUCER,
            "source": "split-plan/task-graph/path-leases",
        },
        "requested_count": count,
        "run_id": request.run_id,
        "schema_version": CURRENT_SCHEMA_VERSION,
        "source_artifacts": {
            "path_leases": path_for_index(run_dir, context["source_paths"]["path_leases"]),
            "request": path_for_index(run_dir, context["source_paths"]["request"]),
            "split_plan": path_for_index(run_dir, context["source_paths"]["split_plan"]),
            "task_graph": path_for_index(run_dir, context["source_paths"]["task_graph"]),
        },
        "temp_bridge": None,
        "updated_at": timestamp,
        "warnings": warnings,
    }
    write_prompt_index_md(run_dir / "prompt-index.md", {**bundle, "prompts": prompt_entries})
    if request.copy_to_temp:
        bridge = write_temp_bridge(request, {**bundle, "prompts": prompt_entries})
        bundle["temp_bridge"] = "temp-bridge.json"
        bundle["evidence_pointers"].append({"path": "temp-bridge.json", "description": "Local temp prompt mirror manifest"})
        warnings.extend(bridge.get("notes", []))
        bundle["warnings"] = _unique(warnings, limit=50)
    write_json(run_dir / "prompt-bundle.json", bundle)
    write_prompt_index_md(run_dir / "prompt-index.md", bundle)
    _write_start_here(run_dir, bundle)
    validation = validate_prompt_bundle(run_dir)
    write_json(run_dir / "prompt-validation.json", validation)
    (run_dir / "prompt-validation-report.md").write_text(_validation_report_md(validation), encoding="utf-8")
    return PromptBundleResult(
        errors=list(validation.get("errors", [])),
        prompt_bundle_path=run_dir / "prompt-bundle.json",
        prompt_count=len(prompt_entries),
        prompt_index_path=run_dir / "prompt-index.json",
        prompts=prompt_entries,
        run_dir=run_dir,
        run_id=request.run_id,
        temp_bridge_path=run_dir / "temp-bridge.json" if request.copy_to_temp else None,
        warnings=list(bundle.get("warnings", [])),
    )


def validate_prompt_file(path: Path) -> list[str]:
    """Validate required sections and safety constraints for one prompt."""
    errors: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return [f"{rel(path)} does not exist"]
    if "# Patch Swarm Prompt" not in text:
        errors.append(f"{rel(path)} missing # Patch Swarm Prompt")
    for heading in REQUIRED_PROMPT_SECTIONS:
        if heading not in text:
            errors.append(f"{rel(path)} missing {heading}")
    for required in ["CODEx_THREAD_TITLE", "PASTE_TO_CODEX"]:
        if required not in text:
            errors.append(f"{rel(path)} missing {required}")
    for pattern, label in SECRET_VALUE_PATTERNS:
        if pattern.search(text):
            errors.append(f"{rel(path)} contains secret-like {label}")
    return errors


def validate_prompt_bundle(run_dir: Path) -> dict[str, Any]:
    """Validate prompt bundle metadata, index references, prompt sections, and hashes."""
    run_dir = resolve_path(run_dir) or run_dir
    errors: list[str] = []
    warnings: list[str] = []
    checked: list[dict[str, Any]] = []
    bundle = read_json_artifact(run_dir / "prompt-bundle.json")
    index = read_json_artifact(run_dir / "prompt-index.json")
    prompts = index.get("prompts") if isinstance(index.get("prompts"), list) else []
    bundle_prompts = bundle.get("prompts") if isinstance(bundle.get("prompts"), list) else []
    requested = int(bundle.get("requested_count") or len(prompts))
    if bundle.get("artifact_type") != "prompt-bundle":
        errors.append("prompt-bundle artifact_type must be prompt-bundle")
    if index.get("artifact_type") != "prompt-index":
        errors.append("prompt-index artifact_type must be prompt-index")
    if len(prompts) != requested:
        errors.append(f"prompt count mismatch: expected {requested}, found {len(prompts)}")
    if len(bundle_prompts) != len(prompts):
        errors.append("prompt-bundle prompts length must match prompt-index prompts length")
    for entry in prompts:
        if not isinstance(entry, dict):
            errors.append("prompt-index prompts entries must be objects")
            continue
        prompt_path = resolve_index_entry_path(run_dir, str(entry.get("path") or ""))
        prompt_errors = validate_prompt_file(prompt_path)
        errors.extend(prompt_errors)
        if prompt_path.exists():
            actual = sha256_file(prompt_path)
            if actual != str(entry.get("sha256") or ""):
                errors.append(f"{entry.get('path')} sha256 mismatch")
            checked.append({"path": str(entry.get("path") or ""), "sha256": actual})
    if bundle.get("temp_bridge"):
        bridge = read_json_artifact(run_dir / "temp-bridge.json")
        current_prompt = resolve_path(str(bridge.get("current_prompt") or ""))
        if not current_prompt or not current_prompt.exists():
            errors.append("temp bridge current_prompt does not exist")
        temp_index = resolve_path(str(bridge.get("temp_dir") or "")) / "prompt-index.md" if bridge.get("temp_dir") else None
        if temp_index and not temp_index.exists():
            errors.append("temp bridge prompt-index.md does not exist")
    return {
        "checked_prompts": checked,
        "errors": errors,
        "ok": not errors,
        "prompt_count": len(prompts),
        "run_id": str(bundle.get("run_id") or index.get("run_id") or run_dir.name),
        "warnings": warnings,
    }


def build_proreq_fixture(
    run_dir: Path,
    *,
    run_id: str,
    count: int,
    timestamp: str,
    lane: str = "all",
    copy_to_temp: bool = False,
    temp_dir: Path | None = None,
) -> PromptBundleResult:
    """Generate deterministic fixture inputs and prompt bundle."""
    write_fixture_inputs(run_dir, run_id=run_id, timestamp=timestamp, task_count=FIXTURE_TASK_COUNT)
    return write_prompt_bundle(
        PromptBundleRequest(
            copy_to_temp=copy_to_temp,
            count=count,
            fixed_timestamp=timestamp,
            lane=lane,
            run_dir=run_dir,
            run_id=run_id,
            temp_dir=temp_dir,
        )
    )


def print_policy() -> dict[str, Any]:
    """Return local prompt generator policy."""
    return {
        "default_count": DEFAULT_PROMPT_COUNT,
        "lanes": sorted(LANES),
        "max_count": MAX_PROMPT_COUNT,
        "no_api_calls_by_default": True,
        "no_live_ai_calls": True,
        "no_secrets": True,
        "operator_copy_paste_flow": True,
        "prompt_types": sorted(PROMPT_TYPES),
        "required_sections": REQUIRED_PROMPT_SECTIONS,
        "schema_version": CURRENT_SCHEMA_VERSION,
    }


def _result_payload(result: PromptBundleResult, *, command: str, lane: str) -> dict[str, Any]:
    return {
        "artifacts": [
            rel(result.prompt_bundle_path),
            rel(result.prompt_index_path),
            rel(result.run_dir / "prompt-index.md"),
            rel(result.run_dir / "prompt-validation.json"),
            rel(result.run_dir / "prompt-validation-report.md"),
        ],
        "command": command,
        "errors": result.errors,
        "lane": lane,
        "ok": not result.errors,
        "prompt_bundle": rel(result.prompt_bundle_path),
        "prompt_count": result.prompt_count,
        "prompt_index": rel(result.prompt_index_path),
        "prompt_index_md": rel(result.run_dir / "prompt-index.md"),
        "run_dir": rel(result.run_dir),
        "run_id": result.run_id,
        "state": "prompt_bundle_created" if not result.errors else "prompt_bundle_failed",
        "temp_bridge": rel(result.temp_bridge_path) if result.temp_bridge_path else "",
        "warnings": result.warnings,
    }


def _request_from_args(args: argparse.Namespace, *, default_run_id: str = "proreq-fixture") -> PromptBundleRequest:
    run_dir = resolve_path(getattr(args, "run_dir", "") or None, default=DEFAULT_RUN_DIR)
    assert run_dir is not None
    run_id = getattr(args, "run_id", "") or run_dir.name or default_run_id
    temp_dir = resolve_path(getattr(args, "temp_dir", "") or None, default=DEFAULT_TEMP_ROOT / run_id)
    return PromptBundleRequest(
        copy_to_temp=bool(getattr(args, "copy_to_temp", False)),
        count=validate_prompt_count(int(getattr(args, "count", DEFAULT_PROMPT_COUNT) or DEFAULT_PROMPT_COUNT)),
        fixed_timestamp=getattr(args, "fixed_timestamp", "") or None,
        lane=normalize_lane(getattr(args, "lane", "all")),
        out_dir=resolve_path(getattr(args, "out_dir", "") or None),
        path_leases_path=resolve_path(getattr(args, "path_leases", "") or None),
        request_file=resolve_path(getattr(args, "request_file", "") or None),
        run_dir=run_dir,
        run_id=run_id,
        split_plan_path=resolve_path(getattr(args, "split_plan", "") or None),
        task_graph_path=resolve_path(getattr(args, "task_graph", "") or None),
        temp_dir=temp_dir,
    )


def run_generate_from_args(args: argparse.Namespace, *, command: str = "parallel-delivery patch-swarm prompts") -> tuple[dict[str, Any], int]:
    try:
        request = _request_from_args(args)
        timestamp = request.fixed_timestamp or utc_now()
        missing = [name for name in ["request.md", "split-plan.json", "task-graph.json", "path-leases.json"] if not (request.run_dir / name).exists()]
        if missing:
            write_fixture_inputs(request.run_dir, run_id=request.run_id, timestamp=timestamp, task_count=FIXTURE_TASK_COUNT)
        result = write_prompt_bundle(request)
        payload = _result_payload(result, command=command, lane=request.lane)
        return payload, 0 if payload["ok"] else 1
    except PromptBundleError as exc:
        payload = {
            "artifacts": [],
            "command": command,
            "errors": [str(exc)],
            "lane": getattr(args, "lane", "all"),
            "ok": False,
            "prompt_count": 0,
            "run_id": getattr(args, "run_id", "") or "unknown",
            "state": "prompt_bundle_failed",
            "warnings": [],
        }
        return payload, 2


def command_write_fixture(args: argparse.Namespace) -> int:
    try:
        run_dir = resolve_path(args.run_dir, default=DEFAULT_RUN_DIR)
        assert run_dir is not None
        run_id = args.run_id or run_dir.name or "proreq-fixture"
        result = build_proreq_fixture(
            run_dir,
            copy_to_temp=bool(args.copy_to_temp),
            count=validate_prompt_count(args.count),
            lane=normalize_lane(args.lane),
            run_id=run_id,
            temp_dir=resolve_path(args.temp_dir or None, default=DEFAULT_TEMP_ROOT / run_id),
            timestamp=args.fixed_timestamp or utc_now(),
        )
        payload = _result_payload(result, command="parallel-delivery patch-swarm prompts", lane=normalize_lane(args.lane))
        print(stable_json_dumps(payload) if args.json else f"{payload['state']} {payload['prompt_count']} prompts {payload['run_dir']}", end="" if args.json else "\n")
        return 0 if payload["ok"] else 1
    except PromptBundleError as exc:
        payload = {"ok": False, "state": "prompt_bundle_failed", "errors": [str(exc)], "warnings": []}
        print(stable_json_dumps(payload) if args.json else str(exc), end="" if args.json else "\n", file=sys.stdout if args.json else sys.stderr)
        return 2


def command_generate(args: argparse.Namespace) -> int:
    payload, code = run_generate_from_args(args)
    print(stable_json_dumps(payload) if args.json else f"{payload['state']} {payload.get('prompt_count', 0)} prompts", end="" if args.json else "\n")
    return code


def command_validate_bundle(args: argparse.Namespace) -> int:
    try:
        run_dir = resolve_path(args.run_dir, default=DEFAULT_RUN_DIR)
        assert run_dir is not None
        payload = validate_prompt_bundle(run_dir)
        print(stable_json_dumps(payload) if args.json else ("passed" if payload["ok"] else "failed"), end="" if args.json else "\n")
        return 0 if payload["ok"] else 1
    except PromptBundleError as exc:
        payload = {"checked_prompts": [], "errors": [str(exc)], "ok": False, "prompt_count": 0, "run_id": "", "warnings": []}
        print(stable_json_dumps(payload) if args.json else str(exc), end="" if args.json else "\n", file=sys.stdout if args.json else sys.stderr)
        return 2


def command_print_policy(args: argparse.Namespace) -> int:
    payload = print_policy()
    print(stable_json_dumps(payload) if args.json else json.dumps(payload, indent=2, sort_keys=True), end="" if args.json else "\n")
    return 0


def add_common_generation_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--run-dir", default=str(DEFAULT_RUN_DIR.relative_to(ROOT)))
    parser.add_argument("--split-plan", default="")
    parser.add_argument("--task-graph", default="")
    parser.add_argument("--path-leases", default="")
    parser.add_argument("--request-file", default="")
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--temp-dir", default="")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--count", type=int, default=DEFAULT_PROMPT_COUNT)
    parser.add_argument("--lane", default="all", choices=sorted(LANES))
    parser.add_argument("--fixed-timestamp", default="")
    parser.add_argument("--copy-to-temp", action="store_true")
    parser.add_argument("--chatgpt-pro", action="store_true", help="Document intent for ChatGPT Pro copy/paste prompts; no live call is made.")
    parser.add_argument("--json", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate local Patch Swarm ChatGPT Pro prompt bundles.")
    sub = parser.add_subparsers(dest="command", required=True)

    fixture = sub.add_parser("write-fixture", help="Write deterministic fixture inputs and prompt bundle.")
    add_common_generation_args(fixture)
    fixture.set_defaults(func=command_write_fixture)

    generate = sub.add_parser("generate", help="Generate prompts from existing run artifacts.")
    add_common_generation_args(generate)
    generate.set_defaults(func=command_generate)

    validate = sub.add_parser("validate-bundle", help="Validate prompt bundle artifacts.")
    validate.add_argument("--run-dir", default=str(DEFAULT_RUN_DIR.relative_to(ROOT)))
    validate.add_argument("--json", action="store_true")
    validate.set_defaults(func=command_validate_bundle)

    policy = sub.add_parser("print-policy", help="Print local prompt generation policy.")
    policy.add_argument("--json", action="store_true")
    policy.set_defaults(func=command_print_policy)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
