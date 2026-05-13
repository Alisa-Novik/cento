#!/usr/bin/env python3
"""Local Patch Swarm Codex worker packet generator.

This helper emits paste-ready Codex worker packets from split-plan, task-graph,
and path-lease artifacts. It is local-only: it does not dispatch workers, call
model APIs, apply patches, or mutate Taskstream/Redmine state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CURRENT_SCHEMA_VERSION = 1
DEFAULT_PACKET_COUNT = 10
PRODUCER = "cento.parallel-delivery.codex-packets"

SUPPORTED_LANES = {
    "builder",
    "validator",
    "docs-evidence",
    "coordinator",
    "integrator",
    "human-handoff",
}
LANE_ORDER = ["builder", "validator", "docs-evidence", "coordinator", "integrator"]
LANE_PROFILES = {
    "builder": ("python-builder", "medium"),
    "validator": ("test-writer", "low"),
    "docs-evidence": ("docs-evidence-writer", "low"),
    "coordinator": ("factory-planner", "medium"),
    "integrator": ("safe-integrator", "high"),
    "human-handoff": ("human-operator", "human"),
}

REQUIRED_PACKET_SECTIONS = [
    "## Thread Title",
    "## Task ID",
    "## Mission",
    "## Discovery Commands",
    "## Owned Write Paths",
    "## Read-Only Paths",
    "## Prohibited Paths",
    "## Implementation Steps",
    "## Expected Files Changed",
    "## Tests And Validation",
    "## Evidence Path",
    "## Patch Bundle Output Instructions",
    "## Handoff Note Format",
    "## Failure / Blocker Protocol",
    "## Safety Rules",
    "## Acceptance Criteria",
]

SECRET_PROTECTED_PATTERNS = [
    ".env",
    ".env.",
    ".env.mcp",
    "OPENAI_API_KEY",
    "sk-",
    "api_key",
    "token=",
    "password=",
    "credential",
]

BASE_PROHIBITED_PATHS = [
    ".env",
    ".env.*",
    ".env.mcp",
    ".git/**",
    "**/*.pem",
    "**/*.key",
    "**/*secret*",
    "**/*token*",
    "**/*credential*",
    "paths outside owned write paths",
    "read-only paths",
    "other tasks' owned paths",
]

SECRET_VALUE_REGEXES = [
    re.compile(r"OPENAI_API_KEY\s*=\s*\S+", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\b(api_key|token|password)\s*=\s*[A-Za-z0-9_./+=-]{8,}\b", re.IGNORECASE),
]


class CodexPacketError(Exception):
    """Raised when worker packet generation or validation fails."""


@dataclass(frozen=True)
class CodexPacketRequest:
    run_id: str
    run_dir: Path
    count: int | None = None
    split_plan_path: Path | None = None
    task_graph_path: Path | None = None
    path_leases_path: Path | None = None
    out_dir: Path | None = None
    fixed_timestamp: str | None = None


@dataclass(frozen=True)
class CodexPacketSpec:
    packet_id: str
    task_id: str
    title: str
    lane: str
    risk_tier: str
    worker_profile: str
    owned_write_paths: list[str]
    read_only_paths: list[str]
    prohibited_paths: list[str]
    validation_commands: list[str]
    evidence_path: str
    patch_bundle_path: str
    copy_order: int
    requires_manual_review: bool
    mission: str
    expected_files_changed: list[str]
    implementation_steps: list[str]
    acceptance_criteria: list[str]
    dependencies: list[str]
    risk_notes: list[str]


@dataclass(frozen=True)
class CodexPacketResult:
    run_id: str
    run_dir: Path
    packet_count: int
    bundle_path: Path
    index_path: Path
    packets: list[dict[str, Any]]
    warnings: list[str]
    errors: list[str]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stable_json_dumps(payload: Any) -> str:
    """Return deterministic JSON with sorted keys, two-space indent, and trailing newline."""
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write deterministic JSON artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json_dumps(payload), encoding="utf-8")


def sha256_file(path: Path) -> str:
    """Return sha256 digest for packet index validation."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def run_dir_text(run_dir: Path) -> str:
    return rel(run_dir)


def safe_read_json(path: Path) -> dict[str, Any]:
    """Read JSON artifact safely and fail clearly."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CodexPacketError(f"required JSON artifact missing: {rel(path)}") from exc
    except json.JSONDecodeError as exc:
        raise CodexPacketError(f"invalid JSON in {rel(path)}: {exc}") from exc
    if not isinstance(payload, dict):
        raise CodexPacketError(f"expected JSON object in {rel(path)}")
    return payload


def normalize_relative_path(value: str) -> str:
    path = str(value).replace("\\", "/").strip().strip("/")
    if not path:
        raise CodexPacketError("path must not be empty")
    if path.startswith("/"):
        raise CodexPacketError(f"absolute paths are not allowed: {value}")
    if ".." in path.split("/"):
        raise CodexPacketError(f"parent traversal is not allowed: {value}")
    return path


def normalize_path_list(paths: Any) -> list[str]:
    if not isinstance(paths, list):
        return []
    normalized: list[str] = []
    for item in paths:
        if not isinstance(item, str):
            continue
        normalized.append(normalize_relative_path(item))
    return sorted(dict.fromkeys(normalized))


def unique_text(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def redact_secret_like_text(text: str) -> tuple[str, list[str]]:
    """Redact obvious secret-like strings from packet content."""
    warnings: list[str] = []
    redacted = text
    for regex in SECRET_VALUE_REGEXES:
        if regex.search(redacted):
            warnings.append(f"redacted secret-like pattern: {regex.pattern}")
            redacted = regex.sub("[REDACTED_SECRET_LIKE_VALUE]", redacted)
    return redacted, warnings


def validate_packet_count(count: int | None, task_count: int) -> int:
    """Resolve requested packet count; real runs emit one packet for every task."""
    if task_count < 1:
        raise CodexPacketError("task graph has no tasks")
    if count is None:
        return task_count
    if count < task_count:
        raise CodexPacketError(f"requested count {count} is less than task count {task_count}")
    return task_count


def load_worker_context(request: CodexPacketRequest) -> dict[str, Any]:
    """Load split plan, task graph, path leases, and derive task/lease context."""
    run_dir = resolve_path(request.run_dir)
    split_path = resolve_path(request.split_plan_path) if request.split_plan_path else run_dir / "split-plan.json"
    graph_path = resolve_path(request.task_graph_path) if request.task_graph_path else run_dir / "task-graph.json"
    leases_path = resolve_path(request.path_leases_path) if request.path_leases_path else run_dir / "path-leases.json"
    request_path = run_dir / "request.md"

    if not leases_path.exists():
        raise CodexPacketError(f"path-leases.json is required for real packet generation: {rel(leases_path)}")

    split_plan = safe_read_json(split_path)
    task_graph = safe_read_json(graph_path)
    path_leases = safe_read_json(leases_path)

    tasks = [task for task in split_plan.get("tasks", []) if isinstance(task, dict)]
    if not tasks and isinstance(task_graph.get("nodes"), list):
        tasks = [node for node in task_graph["nodes"] if isinstance(node, dict)]
    resolved_count = validate_packet_count(request.count, len(tasks))
    tasks = tasks[:resolved_count]

    run_id = request.run_id or str(split_plan.get("run_id") or path_leases.get("run_id") or run_dir.name)
    request_text = request_path.read_text(encoding="utf-8") if request_path.exists() else ""
    return {
        "run_id": run_id,
        "run_dir": run_dir,
        "run_dir_text": run_dir_text(run_dir),
        "request_text": request_text,
        "split_plan": split_plan,
        "task_graph": task_graph,
        "path_leases": path_leases,
        "tasks": tasks,
        "timestamp": request.fixed_timestamp or utc_now(),
    }


def path_overlaps(left: str, right: str) -> bool:
    left = left.rstrip("/")
    right = right.rstrip("/")
    return left == right or left.startswith(right + "/") or right.startswith(left + "/")


def _lease_by_task(path_leases: dict[str, Any]) -> dict[str, dict[str, Any]]:
    leases: dict[str, dict[str, Any]] = {}
    for item in path_leases.get("leases", []):
        if not isinstance(item, dict):
            continue
        task_id = str(item.get("task_id") or "")
        if task_id:
            leases[task_id] = item
    return leases


def _task_id(task: dict[str, Any], index: int) -> str:
    return str(task.get("task_id") or task.get("id") or f"task-{index:04d}")


def _task_lane(task: dict[str, Any]) -> str:
    lane = str(task.get("lane") or "").strip() or "builder"
    if bool(task.get("human_handoff")):
        lane = "human-handoff"
    if lane not in SUPPORTED_LANES:
        raise CodexPacketError(f"unsupported task lane: {lane}")
    return lane


def prohibited_paths_for_task(task: dict[str, Any], lease: dict[str, Any], all_leases: list[dict[str, Any]]) -> list[str]:
    """Return protected paths, read-only paths, and other tasks' owned paths."""
    task_id = str(task.get("task_id") or task.get("id") or lease.get("task_id") or "")
    owned = set(normalize_path_list(lease.get("owned_paths", [])))
    read_only = normalize_path_list(lease.get("read_only_paths", []))
    guarded = normalize_path_list(lease.get("guarded_paths", []))
    protected = normalize_path_list(lease.get("protected_paths", []))
    other_owned: list[str] = []
    for other in all_leases:
        if not isinstance(other, dict) or str(other.get("task_id") or "") == task_id:
            continue
        other_owned.extend(normalize_path_list(other.get("owned_paths", [])))
    prohibited = [*BASE_PROHIBITED_PATHS, *read_only, *guarded, *protected]
    prohibited.extend(path for path in other_owned if path not in owned)
    return unique_text(prohibited)


def lane_guidance(lane: str) -> str:
    """Return lane-specific implementation guidance."""
    return {
        "builder": (
            "Keep implementation small and bounded. Change the minimal set of owned files, "
            "run the listed validation commands, and produce the patch bundle artifacts."
        ),
        "validator": (
            "Focus on tests, fixtures, validation harnesses, negative cases, and clear evidence "
            "showing failing and passing checks."
        ),
        "docs-evidence": (
            "Focus on docs, runbooks, evidence summaries, and operator-facing wording. Do not "
            "change source code unless that source path is explicitly leased."
        ),
        "coordinator": (
            "Coordinate manifest, schema, CLI routing, docs, and registry consistency without broad rewrites."
        ),
        "integrator": (
            "Plan or validate integration only. Do not apply patches unless the owned lease explicitly "
            "allows it and all ordering/evidence checks are satisfied."
        ),
        "human-handoff": (
            "This task is not safe for automated Codex implementation. Do not edit repo files. "
            "Produce a handoff note with decision points, required human action, and evidence."
        ),
    }[lane]


def build_packet_specs(context: dict[str, Any], *, count: int | None = None) -> list[CodexPacketSpec]:
    """Build deterministic packet specs for every task."""
    tasks = [task for task in context["tasks"] if isinstance(task, dict)]
    if count is not None:
        validate_packet_count(count, len(tasks))
    leases = [lease for lease in context["path_leases"].get("leases", []) if isinstance(lease, dict)]
    leases_by_task = _lease_by_task(context["path_leases"])
    specs: list[CodexPacketSpec] = []
    for index, task in enumerate(tasks, start=1):
        task_id = _task_id(task, index)
        lane = _task_lane(task)
        human = lane == "human-handoff" or bool(task.get("human_handoff"))
        lease = leases_by_task.get(task_id, {})
        if not lease and not human:
            raise CodexPacketError(f"task {task_id} has no path lease")

        profile, risk = LANE_PROFILES[lane]
        worker_profile = str(task.get("worker_profile") or lease.get("worker_profile") or profile)
        risk_tier = str(task.get("risk_tier") or lease.get("risk_tier") or risk)
        owned = [] if human else normalize_path_list(lease.get("owned_paths", []))
        read_only = normalize_path_list(lease.get("read_only_paths", task.get("read_only_paths", [])))
        prohibited = prohibited_paths_for_task({"task_id": task_id}, lease, leases) if lease else unique_text(BASE_PROHIBITED_PATHS + read_only)
        validation_commands = text_list(task.get("validation_commands")) or [
            "python3 -m json.tool data/tools.json >/dev/null",
            "python3 -m json.tool data/cento-cli.json >/dev/null",
        ]
        dependencies = text_list(task.get("dependencies") or task.get("depends_on") or lease.get("dependency_gates"))
        dirty_owned = normalize_path_list(lease.get("dirty_owned_paths", []))
        guarded = normalize_path_list(lease.get("guarded_paths", []))
        protected = normalize_path_list(lease.get("protected_paths", []))
        risk_notes = []
        if dirty_owned:
            risk_notes.append("Dirty owned paths are flagged in the lease: " + ", ".join(dirty_owned))
        if guarded:
            risk_notes.append("Guarded paths require blocker handling unless explicitly owned: " + ", ".join(guarded))
        if protected:
            risk_notes.append("Protected paths must not be edited: " + ", ".join(protected))
        if dependencies:
            risk_notes.append("Dependency gates: " + ", ".join(dependencies))

        expected = [] if human else (text_list(task.get("expected_artifacts")) or owned)
        steps = [
            "Run the discovery commands before editing anything.",
            "Inspect only the listed read-only context and owned paths needed for the task.",
            lane_guidance(lane),
            "Make the smallest safe change inside Owned Write Paths, or write a blocker handoff if that is impossible.",
            "Run validation commands or record why a command could not run.",
            "Write the patch bundle, diff, handoff note, and evidence files before reporting done.",
        ]
        if human:
            steps = [
                "Run discovery and inspect the task context only.",
                "Do not edit repo files.",
                "Write a handoff note with decision points, required human action, evidence, blockers, and suggested next action.",
            ]
        acceptance = text_list(task.get("acceptance_contract")) or [
            "Validation passes or exact failure evidence is recorded.",
            "Evidence is written under the task evidence path.",
            "Patch bundle and handoff artifacts are complete.",
        ]
        specs.append(
            CodexPacketSpec(
                packet_id=f"packet-{task_id}",
                task_id=task_id,
                title=str(task.get("title") or task.get("summary") or task_id),
                lane=lane,
                risk_tier=risk_tier,
                worker_profile=worker_profile,
                owned_write_paths=owned,
                read_only_paths=read_only,
                prohibited_paths=prohibited,
                validation_commands=validation_commands,
                evidence_path=f"workers/{task_id}/evidence/",
                patch_bundle_path=f"patch-bundles/{task_id}.patch-bundle.json",
                copy_order=index,
                requires_manual_review=bool(human or lease.get("requires_manual_review")),
                mission=str(task.get("summary") or task.get("story") or task.get("title") or task_id),
                expected_files_changed=expected,
                implementation_steps=steps,
                acceptance_criteria=acceptance,
                dependencies=dependencies,
                risk_notes=risk_notes,
            )
        )
    return specs


def md_list(items: list[str], *, code: bool = True) -> str:
    if not items:
        return "- None"
    if code:
        return "\n".join(f"- `{item}`" for item in items)
    return "\n".join(f"- {item}" for item in items)


def shell_quote(path: str) -> str:
    return shlex.quote(path)


def patch_bundle_instructions(run_id: str, task_id: str) -> str:
    """Return patch bundle output schema and instructions."""
    schema = {
        "schema_version": 1,
        "artifact_type": "patch-bundle",
        "run_id": run_id,
        "task_id": task_id,
        "base_ref": "string",
        "worker_id": "codex",
        "claimed_paths": [],
        "changed_paths": [],
        "diff_path": f"patch-bundles/{task_id}.diff",
        "summary": "string",
        "tests_run": [],
        "evidence_files": [],
        "handoff_note": f"workers/{task_id}/handoff.md",
        "risks": [],
        "requires_manual_review": False,
    }
    return (
        f"Write these artifacts under the packet run directory:\n\n"
        f"- `workers/{task_id}/handoff.md`\n"
        f"- `workers/{task_id}/evidence/`\n"
        f"- `patch-bundles/{task_id}.patch-bundle.json`\n"
        f"- `patch-bundles/{task_id}.diff`\n\n"
        "The patch bundle must include summary, files changed, tests run, evidence files, risks, blockers, "
        "and the manual review flag. Do not fabricate test results. If validation cannot run, record why in "
        "the handoff note.\n\n"
        "```json\n"
        f"{stable_json_dumps(schema).rstrip()}\n"
        "```"
    )


def handoff_note_format(task_id: str) -> str:
    """Return required handoff note template."""
    return (
        "```markdown\n"
        "# Codex Worker Handoff\n\n"
        "## Task ID\n\n"
        f"{task_id}\n\n"
        "## Status\n\n"
        "completed | blocked | failed | partial\n\n"
        "## Summary\n\n"
        "## Files Changed\n\n"
        "## Validation Run\n\n"
        "## Evidence Files\n\n"
        "## Blockers\n\n"
        "## Risks\n\n"
        "## Suggested Next Action\n"
        "```"
    )


def failure_protocol_text(task_id: str) -> str:
    return (
        f"Stop and write `workers/{task_id}/handoff.md` if:\n\n"
        "- required edits are outside owned paths\n"
        "- dirty work would be overwritten\n"
        "- validation requires missing secrets or external services\n"
        "- task requires Taskstream/Redmine direct DB writes\n"
        "- acceptance criteria are contradictory\n"
        "- dependency artifacts are missing\n"
        "- protected paths need changes"
    )


def safety_rules_text() -> str:
    """Return safety rules for every Codex packet."""
    return (
        "- Do not edit files outside Owned Write Paths.\n"
        "- Read-only paths may be inspected but not modified.\n"
        "- If a required change appears outside the lease, stop and write a blocker note.\n"
        "- Preserve dirty work. Do not reset, checkout, clean, stash, or overwrite unrelated changes.\n"
        "- Never run git reset, git checkout, git clean, stash, or broad overwrite commands.\n"
        "- Do not copy secrets or inspect local secret files.\n"
        "- Never copy secrets or local environment values.\n"
        "- Never inspect `.env.mcp` or local secret files.\n"
        "- Do not mutate Taskstream/Redmine/story state through direct database writes.\n"
        "- Never mutate Taskstream/Redmine/story state through direct database writes.\n"
        "- Do not mark done unless validation passes and evidence is written.\n"
        "- If you need a path outside the lease, stop and write a blocker handoff note."
    )


def discovery_commands(context: dict[str, Any], spec: CodexPacketSpec) -> str:
    run_dir = context["run_dir_text"]
    commands = [
        "cd /home/alice/projects/cento",
        "git status --short --branch",
        "git status --porcelain=v1",
        f"test -f {shell_quote(run_dir + '/path-leases.json')} && python3 -m json.tool {shell_quote(run_dir + '/path-leases.json')} >/dev/null",
        f"test -f {shell_quote(run_dir + '/split-plan.json')} && python3 -m json.tool {shell_quote(run_dir + '/split-plan.json')} >/dev/null",
        f"test -f {shell_quote(run_dir + '/task-graph.json')} && python3 -m json.tool {shell_quote(run_dir + '/task-graph.json')} >/dev/null",
    ]
    for path in [*spec.owned_write_paths, *spec.read_only_paths]:
        commands.append(f"test -e {shell_quote(path)} || true")
    return "```bash\n" + "\n".join(commands) + "\n```"


def render_codex_packet(context: dict[str, Any], spec: CodexPacketSpec) -> str:
    """Render one Codex worker packet Markdown file."""
    metadata = {
        "artifact_type": "codex-worker-packet",
        "run_id": context["run_id"],
        "schema_version": CURRENT_SCHEMA_VERSION,
        "task_id": spec.task_id,
    }
    dirty_work = (
        "Preserve dirty work. Before editing, inspect status. Never overwrite unrelated hunks; "
        "if dirty owned paths would be overwritten, stop and write a blocker handoff note."
    )
    human_note = ""
    if spec.lane == "human-handoff":
        human_note = (
            "\nThis task is not safe for automated Codex implementation. Do not edit repo files. "
            "Produce a handoff note with decision points, required human action, and evidence.\n"
        )
    packet = f"""# Codex Worker Packet

<!-- cento-artifact: {json.dumps(metadata, sort_keys=True, separators=(",", ":"))} -->

You are Codex working in the Cento repo. You must run discovery first, preserve dirty work, edit only owned write paths, validate deterministically, and leave a patch bundle plus evidence.
{human_note}
## Thread Title

Patch Swarm {spec.task_id} - {spec.title}

## Task ID

`{spec.task_id}`

## Mission

Lane: `{spec.lane}`
Worker profile: `{spec.worker_profile}`
Risk tier: `{spec.risk_tier}`

{spec.mission}

## Discovery Commands

{discovery_commands(context, spec)}

## Owned Write Paths

{md_list(spec.owned_write_paths)}

## Read-Only Paths

{md_list(spec.read_only_paths)}

Read-only paths may be inspected but not modified.

## Prohibited Paths

{md_list(spec.prohibited_paths)}

Do not edit files outside Owned Write Paths. If a required change appears outside the lease, stop and write a blocker note.

## Implementation Steps

{md_list(spec.implementation_steps, code=False)}

## Expected Files Changed

{md_list(spec.expected_files_changed)}

## Tests And Validation

{md_list(spec.validation_commands)}

Do not fabricate test results. If validation cannot run, record why in the handoff note.

## Evidence Path

`{spec.evidence_path}`

## Patch Bundle Output Instructions

{patch_bundle_instructions(context["run_id"], spec.task_id)}

## Handoff Note Format

{handoff_note_format(spec.task_id)}

## Failure / Blocker Protocol

{failure_protocol_text(spec.task_id)}

## Safety Rules

{safety_rules_text()}

## Acceptance Criteria

{md_list(spec.acceptance_criteria, code=False)}

## Run Context

- Run ID: `{context["run_id"]}`
- Run directory: `{context["run_dir_text"]}`
- Packet ID: `{spec.packet_id}`
- Copy order: `{spec.copy_order}`

## Dependencies

{md_list(spec.dependencies)}

## Lane Guidance

{lane_guidance(spec.lane)}

## Risk Notes

{md_list(spec.risk_notes, code=False)}

## Dirty Work Handling

{dirty_work}

## Output Checklist

- Discovery commands run and status reviewed.
- Only Owned Write Paths changed.
- Validation commands run or exact blockers recorded.
- Evidence written under `{spec.evidence_path}`.
- Patch bundle JSON and diff written under `patch-bundles/`.
- Handoff note written to `workers/{spec.task_id}/handoff.md`.
"""
    redacted, _warnings = redact_secret_like_text(packet)
    return redacted


def packet_dir_for_request(request: CodexPacketRequest, run_id: str) -> Path:
    if request.out_dir:
        return resolve_path(request.out_dir)
    fixture_like = run_id.endswith("fixture") or request.run_dir.name.endswith("fixture")
    return resolve_path(request.run_dir) / ("packets" if fixture_like else "codex-packets")


def packet_entry(path: Path, run_dir: Path, spec: CodexPacketSpec) -> dict[str, Any]:
    return {
        "copy_order": spec.copy_order,
        "evidence_path": spec.evidence_path,
        "lane": spec.lane,
        "owned_write_paths": spec.owned_write_paths,
        "packet_id": spec.packet_id,
        "patch_bundle_path": spec.patch_bundle_path,
        "path": path.relative_to(run_dir).as_posix(),
        "prohibited_paths": spec.prohibited_paths,
        "read_only_paths": spec.read_only_paths,
        "requires_manual_review": spec.requires_manual_review,
        "risk_tier": spec.risk_tier,
        "sha256": sha256_file(path),
        "task_id": spec.task_id,
        "title": spec.title,
        "validation_commands": spec.validation_commands,
        "worker_profile": spec.worker_profile,
    }


def write_packet_index_md(path: Path, bundle: dict[str, Any]) -> None:
    """Write human-readable packet index."""
    packets = [item for item in bundle.get("packets", []) if isinstance(item, dict)]
    lane_counts: dict[str, int] = {}
    for item in packets:
        lane = str(item.get("lane") or "unknown")
        lane_counts[lane] = lane_counts.get(lane, 0) + 1
    lines = [
        "# Patch Swarm Codex Worker Packet Index",
        "",
        "## How to Use",
        "",
        "Copy one packet into one Codex thread. Do not dispatch these packets automatically from this generator.",
        "",
        "## Packet Order",
        "",
    ]
    lines.extend(f"{item.get('copy_order')}. `{item.get('task_id')}` - `{item.get('path')}` - {item.get('lane')}" for item in packets)
    lines.extend(["", "## Lane Summary", ""])
    lines.extend(f"- `{lane}`: {count}" for lane, count in sorted(lane_counts.items()))
    lines.extend(["", "## Path Ownership Summary", ""])
    for item in packets:
        lines.append(f"- `{item.get('task_id')}` owns: {', '.join(f'`{p}`' for p in item.get('owned_write_paths', [])) or 'None'}")
    lines.extend(["", "## Validation Summary", ""])
    for item in packets:
        lines.append(f"- `{item.get('task_id')}`: {len(item.get('validation_commands', []))} command(s)")
    lines.extend(
        [
            "",
            "## Handoff Protocol",
            "",
            "Blocked, failed, partial, and completed workers write `workers/<task_id>/handoff.md`.",
            "",
            "## Evidence",
            "",
        ]
    )
    lines.extend(f"- `{item.get('task_id')}` evidence: `{item.get('evidence_path')}`" for item in packets)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_readmes(run_dir: Path, run_id: str) -> None:
    (run_dir / "patch-bundles").mkdir(parents=True, exist_ok=True)
    (run_dir / "handoffs").mkdir(parents=True, exist_ok=True)
    (run_dir / "workers").mkdir(parents=True, exist_ok=True)
    (run_dir / "patch-bundles" / "README.md").write_text(
        f"# Patch Bundles\n\nCodex workers for `{run_id}` write `<task_id>.patch-bundle.json` and `<task_id>.diff` here.\n",
        encoding="utf-8",
    )
    (run_dir / "handoffs" / "README.md").write_text(
        f"# Handoffs\n\nUse worker handoff notes for blocked or human-review tasks in `{run_id}`.\n",
        encoding="utf-8",
    )


def write_packet_bundle(request: CodexPacketRequest) -> CodexPacketResult:
    """Write packet Markdown files, bundle metadata, index JSON/MD, reports, and start-here."""
    context = load_worker_context(request)
    run_dir = context["run_dir"]
    run_id = context["run_id"]
    timestamp = context["timestamp"]
    packet_dir = packet_dir_for_request(request, run_id)
    packet_dir.mkdir(parents=True, exist_ok=True)
    write_readmes(run_dir, run_id)

    specs = build_packet_specs(context, count=request.count)
    packet_entries: list[dict[str, Any]] = []
    warnings: list[str] = []
    for spec in specs:
        packet_path = packet_dir / f"{spec.task_id}-codex-packet.md"
        text = render_codex_packet(context, spec)
        redacted, redact_warnings = redact_secret_like_text(text)
        warnings.extend(f"{spec.task_id}: {warning}" for warning in redact_warnings)
        packet_path.write_text(redacted, encoding="utf-8")
        packet_entries.append(packet_entry(packet_path, run_dir, spec))

    lanes = [lane for lane in LANE_ORDER if any(item["lane"] == lane for item in packet_entries)]
    if any(item["lane"] == "human-handoff" for item in packet_entries):
        lanes.append("human-handoff")

    bundle = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "artifact_type": "codex-packet-bundle",
        "run_id": run_id,
        "created_at": timestamp,
        "updated_at": timestamp,
        "provenance": {
            "producer": PRODUCER,
            "command": "patch-swarm worker-packets",
            "source": "split-plan/task-graph/path-leases",
            "notes": [],
        },
        "source_artifacts": {
            "request": "request.md",
            "split_plan": "split-plan.json",
            "task_graph": "task-graph.json",
            "path_leases": "path-leases.json",
        },
        "packet_count": len(packet_entries),
        "lanes": lanes,
        "policy": {
            "local_only": True,
            "no_api_calls": True,
            "no_secrets": True,
            "owned_paths_required": True,
            "workset_compatible": True,
            "patch_bundle_required": True,
            "evidence_required": True,
        },
        "packets": packet_entries,
        "warnings": warnings,
        "evidence_pointers": ["packet-validation.json", "packet-validation-report.md"],
    }
    index = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "artifact_type": "codex-packet-index",
        "run_id": run_id,
        "created_at": timestamp,
        "updated_at": timestamp,
        "packet_count": len(packet_entries),
        "packets": packet_entries,
    }
    bundle_path = run_dir / "codex-packet-bundle.json"
    index_path = run_dir / "codex-packet-index.json"
    write_json(bundle_path, bundle)
    write_json(index_path, index)
    write_packet_index_md(run_dir / "codex-packet-index.md", bundle)
    write_start_here(run_dir, bundle)
    validation = validate_packet_bundle(run_dir)
    write_json(run_dir / "packet-validation.json", validation)
    write_validation_report(run_dir / "packet-validation-report.md", validation)
    return CodexPacketResult(
        run_id=run_id,
        run_dir=run_dir,
        packet_count=len(packet_entries),
        bundle_path=bundle_path,
        index_path=index_path,
        packets=packet_entries,
        warnings=warnings,
        errors=validation.get("errors", []),
    )


def write_start_here(run_dir: Path, bundle: dict[str, Any]) -> None:
    lines = [
        f"# Patch Swarm Codex Packet Run: {bundle['run_id']}",
        "",
        "## What This Is",
        "",
        "A local-only bundle of paste-ready Codex worker packets. It does not dispatch workers.",
        "",
        "## Artifact Index",
        "",
        "- `codex-packet-bundle.json`",
        "- `codex-packet-index.json`",
        "- `codex-packet-index.md`",
        "- `packets/` or `codex-packets/`",
        "- `patch-bundles/`",
        "- `workers/`",
        "",
        "## Validation Result",
        "",
        "`packet-validation.json` records deterministic packet checks.",
        "",
        "## Operator Next Step",
        "",
        "Open `codex-packet-index.md`, copy one packet into one Codex thread, and collect the worker patch bundle afterward.",
    ]
    (run_dir / "start-here.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def validate_packet_file(path: Path) -> list[str]:
    """Validate required packet sections and secret-safety constraints."""
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    if not text.startswith("# Codex Worker Packet"):
        errors.append(f"{rel(path)} must start with # Codex Worker Packet")
    for heading in REQUIRED_PACKET_SECTIONS:
        if heading not in text:
            errors.append(f"{rel(path)} missing {heading}")
    required_phrases = [
        "Do not edit files outside Owned Write Paths.",
        "Read-only paths may be inspected but not modified.",
        "If a required change appears outside the lease, stop and write a blocker note.",
        "Preserve dirty work. Do not reset, checkout, clean, stash, or overwrite unrelated changes.",
        "Do not copy secrets or inspect local secret files.",
        "Do not mutate Taskstream/Redmine/story state through direct database writes.",
        "Do not mark done unless validation passes and evidence is written.",
        "Do not fabricate test results. If validation cannot run, record why in the handoff note.",
    ]
    for phrase in required_phrases:
        if phrase not in text:
            errors.append(f"{rel(path)} missing safety phrase: {phrase}")
    for regex in SECRET_VALUE_REGEXES:
        if regex.search(text):
            errors.append(f"{rel(path)} contains secret-like value matching {regex.pattern}")
    return errors


def validate_packet_bundle(run_dir: Path) -> dict[str, Any]:
    """Validate bundle metadata, index references, packet sections, hashes, and path ownership."""
    resolved_run_dir = resolve_path(run_dir)
    errors: list[str] = []
    warnings: list[str] = []
    checked_packets: list[str] = []
    try:
        bundle = safe_read_json(resolved_run_dir / "codex-packet-bundle.json")
        index = safe_read_json(resolved_run_dir / "codex-packet-index.json")
    except CodexPacketError as exc:
        return {
            "ok": False,
            "run_id": resolved_run_dir.name,
            "packet_count": 0,
            "checked_packets": [],
            "errors": [str(exc)],
            "warnings": [],
        }
    packets = index.get("packets")
    if not isinstance(packets, list):
        packets = []
        errors.append("codex-packet-index.json packets must be a list")
    if bundle.get("artifact_type") != "codex-packet-bundle":
        errors.append("codex-packet-bundle.json artifact_type must be codex-packet-bundle")
    if index.get("artifact_type") != "codex-packet-index":
        errors.append("codex-packet-index.json artifact_type must be codex-packet-index")
    if int(bundle.get("packet_count") or -1) != len(packets):
        errors.append("bundle packet_count does not match index packet count")

    owned: list[tuple[str, str]] = []
    for item in packets:
        if not isinstance(item, dict):
            errors.append("packet index entry must be an object")
            continue
        task_id = str(item.get("task_id") or "")
        packet_rel = str(item.get("path") or "")
        packet_path = resolved_run_dir / packet_rel
        if not task_id:
            errors.append("packet index entry missing task_id")
        if not packet_path.exists():
            errors.append(f"packet file missing: {packet_rel}")
            continue
        checked_packets.append(task_id)
        errors.extend(validate_packet_file(packet_path))
        digest = sha256_file(packet_path)
        if digest != item.get("sha256"):
            errors.append(f"packet hash mismatch: {task_id}")
        if not isinstance(item.get("owned_write_paths"), list):
            errors.append(f"{task_id} owned_write_paths must be a list")
        elif not item.get("requires_manual_review") and not item.get("owned_write_paths"):
            errors.append(f"{task_id} owned_write_paths must not be empty")
        if not isinstance(item.get("read_only_paths"), list):
            errors.append(f"{task_id} read_only_paths must be a list")
        if not isinstance(item.get("prohibited_paths"), list):
            errors.append(f"{task_id} prohibited_paths must be a list")
        if not isinstance(item.get("validation_commands"), list):
            errors.append(f"{task_id} validation_commands must be a list")
        if not item.get("evidence_path"):
            errors.append(f"{task_id} evidence_path missing")
        if not item.get("patch_bundle_path"):
            errors.append(f"{task_id} patch_bundle_path missing")
        for owned_path in item.get("owned_write_paths") or []:
            try:
                normalized = normalize_relative_path(str(owned_path))
            except CodexPacketError as exc:
                errors.append(f"{task_id} invalid owned path: {exc}")
                continue
            owned.append((task_id, normalized.rstrip("/")))

    for index_a, (task_a, path_a) in enumerate(owned):
        for task_b, path_b in owned[index_a + 1 :]:
            if path_overlaps(path_a, path_b):
                errors.append(f"overlapping owned paths: {task_a}:{path_a} and {task_b}:{path_b}")
    return {
        "ok": not errors,
        "run_id": str(bundle.get("run_id") or index.get("run_id") or resolved_run_dir.name),
        "packet_count": len(packets),
        "checked_packets": checked_packets,
        "errors": errors,
        "warnings": warnings,
    }


def write_validation_report(path: Path, validation: dict[str, Any]) -> None:
    lines = [
        "# Codex Packet Validation Report",
        "",
        "## Summary",
        "",
        f"- OK: `{validation.get('ok')}`",
        f"- Run ID: `{validation.get('run_id')}`",
        f"- Packet count: `{validation.get('packet_count')}`",
        "",
        "## Errors",
        "",
        *(f"- {item}" for item in validation.get("errors", [])),
        *(["- None"] if not validation.get("errors") else []),
        "",
        "## Warnings",
        "",
        *(f"- {item}" for item in validation.get("warnings", [])),
        *(["- None"] if not validation.get("warnings") else []),
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _fixture_task(index: int, lane: str, run_id: str) -> dict[str, Any]:
    task_id = f"task-{index:04d}"
    profile, risk = LANE_PROFILES[lane]
    base = f"workspace/runs/parallel-delivery/{run_id}/task-work/{task_id}"
    return {
        "acceptance_contract": [
            "Packet instructions are bounded to the leased owned path.",
            "Validation commands run or exact blocker evidence is written.",
            "Patch bundle output instructions and handoff note are complete.",
        ],
        "dependencies": [f"task-{index - 1:04d}"] if lane == "integrator" and index > 1 else [],
        "evidence_pointers": [],
        "expected_artifacts": [f"{base}/evidence.json"],
        "human_handoff": False,
        "integration_notes": ["Later Safe Integrator calls decide apply order; this packet does not apply patches."],
        "lane": lane,
        "owned_paths": [base],
        "read_only_paths": ["docs/patch-swarm.md", "docs/parallel-delivery/patch-swarm-artifacts.md"],
        "rejection_triggers": [
            "Touches an unowned path.",
            "Requires a secret, live service, direct DB mutation, or protected path edit.",
            "Cannot produce validation evidence.",
        ],
        "risk_tier": risk,
        "state": "leased",
        "story": f"As a Cento operator, I need a {lane} packet fixture for {task_id}.",
        "summary": f"Produce deterministic {lane} Codex worker packet evidence for {task_id}.",
        "task_id": task_id,
        "title": f"Codex packet fixture {task_id} {lane} lane",
        "validation_commands": [
            "python3 -m json.tool data/tools.json >/dev/null",
            "python3 -m json.tool data/cento-cli.json >/dev/null",
            f"test -f workspace/runs/parallel-delivery/{run_id}/codex-packet-index.json",
        ],
        "worker_profile": profile,
    }


def build_codex_packets_fixture(run_dir: Path, *, run_id: str, count: int, timestamp: str) -> CodexPacketResult:
    """Generate deterministic split plan, task graph, path leases, and worker packets."""
    if count < DEFAULT_PACKET_COUNT:
        raise CodexPacketError("fixture count must be at least 10")
    resolved_run_dir = resolve_path(run_dir)
    resolved_run_dir.mkdir(parents=True, exist_ok=True)
    lanes = [LANE_ORDER[index % len(LANE_ORDER)] for index in range(count)]
    tasks = [_fixture_task(index + 1, lane, run_id) for index, lane in enumerate(lanes)]
    request_text = (
        "# Codex Packets Fixture\n\n"
        "Generate local-only Patch Swarm Codex worker packets covering builder, validator, docs-evidence, coordinator, and integrator lanes.\n"
    )
    (resolved_run_dir / "request.md").write_text(request_text, encoding="utf-8")
    split_plan = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "artifact_type": "split-plan",
        "run_id": run_id,
        "created_at": timestamp,
        "updated_at": timestamp,
        "provenance": {"producer": PRODUCER, "command": "write-fixture", "source": "fixture", "notes": []},
        "evidence_pointers": [],
        "candidate_count": count,
        "candidate_target": count,
        "max_candidate_tasks": count,
        "max_parallel_agents": min(5, count),
        "planner_mode": "fixture",
        "lanes": [*LANE_ORDER, "human-handoff"],
        "request": {
            "request_file": "request.md",
            "summary": "Generate deterministic local Codex worker packets.",
            "title": "Codex Packets Fixture",
        },
        "planning_policy": {
            "avoid_overlapping_owned_paths": True,
            "coarse_lanes_first": True,
            "do_not_blindly_fill_to_target": False,
            "human_handoff_for_subjective_or_device_bound": True,
        },
        "tasks": tasks,
    }
    write_json(resolved_run_dir / "split-plan.json", split_plan)
    task_graph = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "artifact_type": "task-graph",
        "run_id": run_id,
        "created_at": timestamp,
        "updated_at": timestamp,
        "provenance": {"producer": PRODUCER, "command": "write-fixture", "source": "fixture", "notes": []},
        "evidence_pointers": [],
        "max_parallel_agents": min(5, count),
        "nodes": [
            {
                "task_id": task["task_id"],
                "lane": task["lane"],
                "risk_tier": task["risk_tier"],
                "human_handoff": False,
                "owned_paths": task["owned_paths"],
            }
            for task in tasks
        ],
        "edges": [
            {"from": dep, "to": task["task_id"], "type": "depends_on", "reason": "fixture integrator dependency"}
            for task in tasks
            for dep in task["dependencies"]
        ],
        "topological_order": [task["task_id"] for task in tasks],
    }
    write_json(resolved_run_dir / "task-graph.json", task_graph)
    leases = []
    for index, task in enumerate(tasks, start=1):
        leases.append(
            {
                "lease_id": f"lease-{task['task_id']}",
                "task_id": task["task_id"],
                "state": "active",
                "created_at": timestamp,
                "owned_paths": task["owned_paths"],
                "read_only_paths": task["read_only_paths"],
                "guarded_paths": ["data/tools.json", "data/cento-cli.json"],
                "protected_paths": [".env", ".env.*", ".env.mcp", ".git/**"],
                "dirty_owned_paths": [],
                "requires_manual_review": False,
                "minimal_hunk_required": True,
                "dependency_gates": task["dependencies"],
                "parallel_group": f"group-{((index - 1) % 5) + 1}",
            }
        )
    path_leases = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "artifact_type": "path-leases",
        "run_id": run_id,
        "created_at": timestamp,
        "updated_at": timestamp,
        "provenance": {"producer": PRODUCER, "command": "write-fixture", "source": "fixture", "notes": []},
        "evidence_pointers": [],
        "leases": leases,
        "conflicts": [],
    }
    write_json(resolved_run_dir / "path-leases.json", path_leases)
    return write_packet_bundle(
        CodexPacketRequest(
            run_id=run_id,
            run_dir=resolved_run_dir,
            count=count,
            fixed_timestamp=timestamp,
        )
    )


def print_policy() -> dict[str, Any]:
    """Return local worker packet generator policy."""
    return {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "artifact_type": "codex-packet-policy",
        "producer": PRODUCER,
        "local_only": True,
        "no_api_calls": True,
        "no_secrets": True,
        "owned_paths_required": True,
        "workset_compatible": True,
        "patch_bundle_required": True,
        "evidence_required": True,
        "supported_lanes": sorted(SUPPORTED_LANES),
        "required_sections": REQUIRED_PACKET_SECTIONS,
        "secret_protected_patterns": SECRET_PROTECTED_PATTERNS,
        "prohibited_paths": BASE_PROHIBITED_PATHS,
    }


def result_payload(result: CodexPacketResult) -> dict[str, Any]:
    return {
        "ok": not result.errors,
        "run_id": result.run_id,
        "run_dir": rel(result.run_dir),
        "packet_count": result.packet_count,
        "bundle": rel(result.bundle_path),
        "index": rel(result.index_path),
        "packets": result.packets,
        "warnings": result.warnings,
        "errors": result.errors,
    }


def command_print_policy(args: argparse.Namespace) -> int:
    payload = print_policy()
    print(stable_json_dumps(payload) if args.json else stable_json_dumps(payload), end="")
    return 0


def command_write_fixture(args: argparse.Namespace) -> int:
    try:
        result = build_codex_packets_fixture(
            Path(args.run_dir),
            run_id=args.run_id,
            count=args.count,
            timestamp=args.fixed_timestamp or "2026-01-01T00:00:00Z",
        )
        payload = result_payload(result)
    except CodexPacketError as exc:
        payload = {"ok": False, "run_id": args.run_id, "packet_count": 0, "errors": [str(exc)], "warnings": []}
    print(stable_json_dumps(payload) if args.json else stable_json_dumps(payload), end="")
    return 0 if payload.get("ok") else 1


def command_generate(args: argparse.Namespace) -> int:
    try:
        result = write_packet_bundle(
            CodexPacketRequest(
                run_id=args.run_id,
                run_dir=Path(args.run_dir),
                count=args.count,
                split_plan_path=Path(args.split_plan) if args.split_plan else None,
                task_graph_path=Path(args.task_graph) if args.task_graph else None,
                path_leases_path=Path(args.path_leases) if args.path_leases else None,
                fixed_timestamp=args.fixed_timestamp or None,
            )
        )
        payload = result_payload(result)
    except CodexPacketError as exc:
        payload = {"ok": False, "run_id": args.run_id or Path(args.run_dir).name, "packet_count": 0, "errors": [str(exc)], "warnings": []}
    print(stable_json_dumps(payload) if args.json else stable_json_dumps(payload), end="")
    return 0 if payload.get("ok") else 1


def command_validate_bundle(args: argparse.Namespace) -> int:
    payload = validate_packet_bundle(Path(args.run_dir))
    print(stable_json_dumps(payload) if args.json else stable_json_dumps(payload), end="")
    return 0 if payload.get("ok") else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate local Patch Swarm Codex worker packets.")
    sub = parser.add_subparsers(dest="command", required=True)

    policy = sub.add_parser("print-policy", help="Print local worker packet policy.")
    policy.add_argument("--json", action="store_true")
    policy.set_defaults(func=command_print_policy)

    fixture = sub.add_parser("write-fixture", help="Write deterministic fixture inputs and Codex packets.")
    fixture.add_argument("--run-dir", required=True)
    fixture.add_argument("--run-id", default="codex-packets-fixture")
    fixture.add_argument("--count", type=int, default=DEFAULT_PACKET_COUNT)
    fixture.add_argument("--fixed-timestamp", default="2026-01-01T00:00:00Z")
    fixture.add_argument("--json", action="store_true")
    fixture.set_defaults(func=command_write_fixture)

    generate = sub.add_parser("generate", help="Generate Codex packets from existing split/task/lease artifacts.")
    generate.add_argument("--run-dir", required=True)
    generate.add_argument("--run-id", default="")
    generate.add_argument("--count", type=int, default=None)
    generate.add_argument("--split-plan", default="")
    generate.add_argument("--task-graph", default="")
    generate.add_argument("--path-leases", default="")
    generate.add_argument("--fixed-timestamp", default="")
    generate.add_argument("--json", action="store_true")
    generate.set_defaults(func=command_generate)

    validate = sub.add_parser("validate-bundle", help="Validate a generated Codex packet bundle.")
    validate.add_argument("--run-dir", required=True)
    validate.add_argument("--json", action="store_true")
    validate.set_defaults(func=command_validate_bundle)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
