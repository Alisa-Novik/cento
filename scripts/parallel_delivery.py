#!/usr/bin/env python3
"""Parallel AI Delivery coordinator.

This is the durable implementation surface for the roadmap in
docs/parallel-ai-delivery-roadmap.md. It deliberately routes through existing
Cento pipelines: Hard ProReq for requirement/manifests/image prompts, Workset
for parallel worker shape, and local receipts for integration/demo evidence.
"""

from __future__ import annotations

import argparse
from collections import Counter
import difflib
import hashlib
import json
import os
import shutil
import shlex
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


ROOT = Path(__file__).resolve().parents[1]
RUNS_ROOT = ROOT / "workspace" / "runs" / "parallel-delivery"
TRAIN_RUNS_ROOT = RUNS_ROOT / "train"
PATCH_SWARM_RUNS_ROOT = RUNS_ROOT / "patch-swarm"
FACTORY_RUNS_ROOT = ROOT / "workspace" / "runs" / "factory"
SELF_IMPROVE_RUNS_ROOT = ROOT / "workspace" / "runs" / "ai-self-improvement-nightly"
SELF_IMPROVE_E2E_RUNS_ROOT = ROOT / "workspace" / "runs" / "ai-self-improvement-e2e"
CONTINUOUS_PROREQ_ROOT = ROOT / "workspace" / "runs" / "ai-cento-native-continuous-proreq"
PIPELINE_ROOT = ROOT / "workspace" / "runs" / "dev-pipeline-studio" / "docs-pages" / "latest"
SCHEMA_PLAN = "cento.parallel_delivery.plan.v1"
SCHEMA_RECEIPT = "cento.parallel_delivery.receipt.v1"
SCHEMA_VALIDATION = "cento.parallel_delivery.validation.v1"
SCHEMA_TRAIN = "cento.parallel_integration_train.v1"
SCHEMA_TRAIN_QUEUE = "cento.parallel_integration_train.queue.v1"
SCHEMA_TRAIN_RECEIPT = "cento.parallel_integration_train.receipt.v1"
SCHEMA_PATCH_SWARM = "cento.patch_swarm.manifest.v1"
SCHEMA_PATCH_SWARM_PROREQ = "cento.patch_swarm.proreq_execution_manifest.v1"
SCHEMA_PATCH_SWARM_CANDIDATE = "cento.patch_swarm.candidate_patch.v1"
SCHEMA_PATCH_SWARM_RECEIPT = "cento.patch_swarm.receipt.v1"
SCHEMA_PATCH_SWARM_INTEGRATION = "cento.patch_swarm.integration_execution.v1"
SCHEMA_PATCH_SWARM_VALIDATION = "cento.patch_swarm.validation.v1"
SCHEMA_SELF_MANIFEST = "cento.ai_self_improvement_nightly.manifest.v1"
SCHEMA_SELF_PASS = "cento.ai_self_improvement_nightly.pass_summary.v1"
SCHEMA_SELF_GATES = "cento.ai_self_improvement_nightly.validation_gates.v1"
SCHEMA_SELF_METRICS = "cento.ai_self_improvement_nightly.loop_metrics.v1"
SCHEMA_SELF_PROMOTION = "cento.ai_self_improvement_nightly.promotion_recommendation.v1"
SCHEMA_SELF_HANDOFF = "cento.ai_self_improvement_nightly.evidence_handoff.v1"
SCHEMA_SELF_NEXT = "cento.ai_self_improvement_nightly.next_cycle_request.v1"
SCHEMA_SELF_E2E = "cento.ai_self_improvement_e2e.manifest.v1"
SCHEMA_SELF_E2E_VALIDATION = "cento.ai_self_improvement_e2e.validation.v1"
SELF_CRON_BEGIN = "# BEGIN CENTO AI SELF-IMPROVEMENT NIGHTLY"
SELF_CRON_END = "# END CENTO AI SELF-IMPROVEMENT NIGHTLY"

sys.path.insert(0, str(ROOT / "scripts"))
import agent_work_app as app  # noqa: E402
import factory as factory_tool  # noqa: E402
import factory_dispatch_core as factory_dispatch  # noqa: E402
import factory_integrator_core as factory_integrator  # noqa: E402
import parallel_delivery_codex_packets as codex_packets_tool  # noqa: E402
import parallel_delivery_leases as lease_tool  # noqa: E402
import parallel_delivery_patch_bundles as patch_bundles_tool  # noqa: E402
import parallel_delivery_patch_swarm_console as patch_swarm_console_tool  # noqa: E402
import parallel_delivery_planner as planner_tool  # noqa: E402
import parallel_delivery_prompts as prompts_tool  # noqa: E402
import parallel_delivery_release_candidate as release_candidate_tool  # noqa: E402
import parallel_delivery_taskstream as taskstream_tool  # noqa: E402
import parallel_delivery_validation_e2e as validation_e2e_tool  # noqa: E402
import parallel_delivery_worker_status as worker_status_tool  # noqa: E402


BASE_VISION = (
    "Build the next big Cento delivery system: parse requirements once into exclusive "
    "parallel workstreams, run 10 AI workers to produce structured patch/artifact outputs, "
    "then converge through 2-3 integrator/validator lanes where integration and validation "
    "are deterministic first and AI is called only when deterministic gates cannot classify "
    "a conflict, missing evidence, or ambiguity. The target is 2-3 minutes instead of 10 "
    "minutes, with only $3-5 marginal AI cost."
)


WORKSTREAMS: list[dict[str, str]] = [
    {
        "id": "requirements-decomposer",
        "title": "Requirements Decomposer",
        "focus": "parallel delivery plan schema, split policy, exclusive write path detection, and serialized shared-file task generation",
        "image": "requirements intake splitting into 10 owned workstreams and one serialized shared-file lane",
    },
    {
        "id": "workset-10-worker-executor",
        "title": "10 Worker Workset Executor",
        "focus": "max_parallel 10 execution, worker leases, structured patch/artifact outputs, budget reservation, and partial-success continuation",
        "image": "10 worker lanes running in parallel with leases, budgets, structured outputs, and worker receipts",
    },
    {
        "id": "artifact-materializer",
        "title": "Artifact Materializer",
        "focus": "materializing structured worker artifacts into patch bundles without direct worker repo mutation",
        "image": "structured worker artifacts flowing into local materializer and patch bundle receipts",
    },
    {
        "id": "integrator-pool",
        "title": "Integrator Pool",
        "focus": "2-3 deterministic integrator lanes for patch safety, focused validation, release evidence, rollback, and quarantine",
        "image": "three integrator lanes classifying accepted, rejected, and quarantined worker outputs",
    },
    {
        "id": "ai-review-fallback",
        "title": "AI Review Fallback",
        "focus": "only-if-needed AI review packets, reviewer budget caps, advisory output, and deterministic receipt conversion",
        "image": "AI reviewer call appearing only after deterministic validation cannot classify a conflict",
    },
    {
        "id": "cost-latency-ledger",
        "title": "Cost And Latency Ledger",
        "focus": "per-worker timing, queue delay, model usage, hard budget caps, $3-5 marginal target, and 2-3 minute reporting",
        "image": "operator cockpit with timing bars, cost ledger, budget cap, and 2-3 minute target",
    },
    {
        "id": "factory-safe-integrator-bridge",
        "title": "Factory Safe Integrator Bridge",
        "focus": "feeding accepted workset outputs into Factory/Safe Integrator release packets without auto-merging main",
        "image": "workset outputs converging into Safe Integrator branch, rollback plan, and release candidate evidence",
    },
    {
        "id": "dev-pipeline-ui",
        "title": "Dev Pipeline UI",
        "focus": "Run Parallel Delivery UI with worker lanes, validator lanes, fallback calls, timing, cost, and receipts",
        "image": "Dev Pipeline Studio screen with 10 workers, 3 validators, cost/timing counters, and release readiness",
    },
    {
        "id": "observability-and-notify",
        "title": "Observability And Notify",
        "focus": "events, status polling, stuck-run detection, operator notification, and final handoff links",
        "image": "status timeline with stuck-run alert, final notification, and evidence links",
    },
    {
        "id": "benchmark-fixtures",
        "title": "Benchmark Fixtures",
        "focus": "clean run, shared-file conflict, failed validation, budget block, fallback review, and 10-worker benchmark fixtures",
        "image": "fixture matrix showing clean, conflict, validation fail, budget block, and fallback review scenarios",
    },
    {
        "id": "integration-e2e",
        "title": "Integration E2E",
        "focus": "one command for plan, execute, integrate, validate, release packet, and machine-readable receipts",
        "image": "end-to-end command flow from plan to release packet with validation and rollback receipts",
    },
    {
        "id": "demo-task",
        "title": "Demo Task",
        "focus": "small real-looking demo proving 10-lane fanout, deterministic integration, validation, cost ledger, and final evidence",
        "image": "demo task view showing all lanes complete and final release packet ready for review",
    },
]

SELF_IMPROVE_PASS_FOCUS: list[dict[str, str]] = [
    {
        "id": "scope-guardrails",
        "title": "Scope And Guardrails",
        "focus": "Establish the nightly self-improvement objective, autonomy boundary, budget guardrails, scheduler context, nonblocking image policy, and evidence contract.",
    },
    {
        "id": "architecture",
        "title": "Architecture",
        "focus": "Turn pass 1 into durable Cento route contracts, artifact schemas, latest mirror behavior, compute routing, and deterministic fallback behavior.",
    },
    {
        "id": "integration-workset-strategy",
        "title": "Integration And Workset Strategy",
        "focus": "Turn pass 2 into implementation workset strategy, explicit create-file path policy, migration order, rollback points, and promotion prerequisites.",
    },
    {
        "id": "validation-promotion-next-cycle",
        "title": "Validation, Promotion, And Next Cycle",
        "focus": "Turn pass 3 into validation gates, promotion recommendation, repair handling, loop metrics, evidence handoff, and the exact next-night request.",
    },
]

AGENT_PREFERRED_COMPUTE_POLICY = {
    "deterministic_first": True,
    "target_spend_usd_max": 10.0,
    "hard_spend_usd_max": 20.0,
    "optional_model_ceiling": "gpt-4.1-mini",
    "backend_success_depends_on_screenshot_generation": False,
    "codex_claude_utilization_threshold_percent": 30,
    "eligible_work_agent_preference_percent_range": [70, 80],
    "eligible_work_agent_preference_target_percent": 75,
    "policy": (
        "When Codex/Claude weekly utilization is above 30% and capacity remains usable, "
        "prefer Codex/Claude agent lanes over metered OpenAI API for roughly 70-80% of "
        "eligible non-API-only follow-up work. Reserve OpenAI API for structured Responses, "
        "image generation, ProReq planning, and other API-only behavior."
    ),
}

DEMO_TARGET_PATHS = [
    "docs/agent-run-ledger.md",
    "docs/agent-work-coordinator-lane.md",
    "docs/agent-work-deliverables-hub.md",
    "docs/agent-work-docs-evidence-lane.md",
    "docs/agent-work-runtimes.md",
    "docs/agent-work-screenshot-runner.md",
    "docs/agent-work-story-manifest.md",
    "docs/agent-work-validator-lane.md",
    "docs/cento-build.md",
    "docs/cento-workset.md",
]

PATCH_SWARM_OBJECTIVE = (
    "Generate many cheap candidate patches across Codex Exec, Claude Code, and "
    "OpenAI API workers, validate and rank them deterministically, then let one "
    "serialized integration execution hand the winners to Cento Safe Integrator evidence."
)

PATCH_SWARM_PROVIDERS = ["codex-exec", "claude-code", "api-openai"]
PATCH_SWARM_PROVIDER_ALIASES = {
    "codex": "codex-exec",
    "codex_exec": "codex-exec",
    "codex-exec": "codex-exec",
    "claude": "claude-code",
    "claude_code": "claude-code",
    "claude-code": "claude-code",
    "openai": "api-openai",
    "openai-api": "api-openai",
    "api": "api-openai",
    "api-openai": "api-openai",
}
PATCH_SWARM_PROVIDER_RUNTIMES = {
    "codex-exec": {"runtime": "local-command", "runtime_profile": "codex-fast", "mutation_mode": "isolated_worktree"},
    "claude-code": {"runtime": "local-command", "runtime_profile": "claude-code-fast", "mutation_mode": "isolated_worktree"},
    "api-openai": {"runtime": "api-openai", "output_schema": "patch_proposal.v1", "mutation_mode": "structured_artifact"},
}
PATCH_SWARM_API_COST_ESTIMATE_USD = 0.0125
PATCH_SWARM_DEFAULT_LIVE_HARD_CAP_USD = 25.0
PATCH_SWARM_LIVE_ADAPTER_ENV = "CENTO_PATCH_SWARM_LIVE_ADAPTERS"
PATCH_SWARM_API_PROFILE = "api-patch-proposal"

PATCH_SWARM_PROREQ_EXECUTIONS: list[dict[str, Any]] = [
    {
        "id": "request-decomposer",
        "title": "Request Decomposer",
        "focus": "Split the operator objective into patchable tasks, owned paths, protected paths, and validation expectations.",
        "owned_paths": ["docs/parallel-ai-delivery-roadmap.md"],
    },
    {
        "id": "codex-exec-adapter",
        "title": "Codex Exec Adapter",
        "focus": "Prepare candidate prompts and receipt capture for codex exec local-command workers in isolated worktrees.",
        "owned_paths": [".cento/runtimes.yaml"],
    },
    {
        "id": "claude-code-adapter",
        "title": "Claude Code Adapter",
        "focus": "Prepare candidate prompts and receipt capture for Claude Code local-command workers in isolated worktrees.",
        "owned_paths": ["data/agent-runtimes.json"],
    },
    {
        "id": "openai-patch-proposal-adapter",
        "title": "OpenAI Patch Proposal Adapter",
        "focus": "Use structured OpenAI worker artifacts with patch_proposal.v1 and budget receipts.",
        "owned_paths": [".cento/api_workers.yaml"],
    },
    {
        "id": "candidate-normalizer",
        "title": "Candidate Normalizer",
        "focus": "Normalize command-runtime diffs and structured API artifacts into candidate_patch.v1 receipts.",
        "owned_paths": ["scripts/cento_workset.py"],
    },
    {
        "id": "dedupe-clustering",
        "title": "Dedupe And Clustering",
        "focus": "Cluster candidates by execution lane, touched path, normalized patch hash, and duplicate intent.",
        "owned_paths": ["scripts/parallel_delivery.py"],
    },
    {
        "id": "deterministic-validator-fanout",
        "title": "Deterministic Validator Fanout",
        "focus": "Run cheap applyability, ownership, schema, syntax, and focused test gates before any AI review.",
        "owned_paths": ["tests/test_parallel_integration_train.py"],
    },
    {
        "id": "cost-latency-ledger",
        "title": "Cost And Latency Ledger",
        "focus": "Track candidate cost, latency, duplicate saturation, validation pass rate, and cost per accepted patch.",
        "owned_paths": ["scripts/spend_ledger.py"],
    },
    {
        "id": "dev-pipeline-studio-ui",
        "title": "Dev Pipeline Studio UI",
        "focus": "Expose provider mix, candidate totals, dedupe clusters, validation, winners, and integration status in the existing UI.",
        "owned_paths": ["templates/agent-work-app/app.js"],
    },
    {
        "id": "autopilot-coordinator-hooks",
        "title": "Autopilot Coordinator Hooks",
        "focus": "Provide dry-run launch/status/retry/budget-stop artifacts for future Walk Autopilot coordination.",
        "owned_paths": ["scripts/walk_autopilot.py"],
    },
]

PATCH_SWARM_INTEGRATOR = {
    "id": "dedicated-integrator",
    "title": "Dedicated Patch Swarm Integrator",
    "focus": "Consume all ten ProReq execution outputs, select winners, resolve conflicts, and write the Safe Integrator handoff.",
}


def now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    if isinstance(payload, dict):
        return payload
    return {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")


def is_parallel_delivery_run_dir(path: Path) -> bool:
    return path.is_dir() and (path / "implementation_manifest.json").exists()


def is_parallel_delivery_validatable_run_dir(path: Path) -> bool:
    return (
        is_parallel_delivery_run_dir(path)
        and (path / "proreq_receipt.json").exists()
        and (path / "execution_manifest.json").exists()
    )


def is_patch_swarm_fixture_e2e_run_dir(path: Path) -> bool:
    return (
        path.is_dir()
        and (path / "validation-summary.json").exists()
        and (path / "split-plan.json").exists()
        and (path / "path-leases.json").exists()
        and (path / "integration" / "integration-receipt.json").exists()
    )


def latest_patch_swarm_fixture_e2e_run_dir(root: Path | None = None) -> Path | None:
    search_root = root or RUNS_ROOT
    if not search_root.exists():
        return None
    candidates = [
        path.parent
        for path in search_root.glob("**/validation-summary.json")
        if is_patch_swarm_fixture_e2e_run_dir(path.parent)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def selected_patch_swarm_fixture_e2e_run_dir(path: Path) -> Path | None:
    if is_patch_swarm_fixture_e2e_run_dir(path):
        return path
    return latest_patch_swarm_fixture_e2e_run_dir(path)


def latest_run_dir() -> Path | None:
    if not RUNS_ROOT.exists():
        return None
    candidates = [path for path in RUNS_ROOT.iterdir() if is_parallel_delivery_run_dir(path)]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def latest_validatable_run_dir() -> Path | None:
    if not RUNS_ROOT.exists():
        return None
    candidates = [path for path in RUNS_ROOT.iterdir() if is_parallel_delivery_validatable_run_dir(path)]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def resolve_run_dir(value: str | None, *, create: bool = False) -> Path:
    if value:
        path = Path(value)
        if not path.is_absolute():
            path = ROOT / path
    else:
        path = latest_run_dir() if not create else RUNS_ROOT / now_stamp()
        if path is None:
            path = RUNS_ROOT / now_stamp()
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_validation_run_dir(value: str | None) -> Path:
    if value:
        return resolve_run_dir(value)
    return latest_validatable_run_dir() or latest_run_dir() or (latest_patch_swarm_fixture_e2e_run_dir() or RUNS_ROOT / now_stamp())


@contextmanager
def scoped_env(updates: dict[str, str]) -> Iterator[None]:
    old_values = {key: os.environ.get(key) for key in updates}
    try:
        for key, value in updates.items():
            os.environ[key] = value
        yield
    finally:
        for key, value in old_values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def pass_prompt(workstream: dict[str, str]) -> str:
    return (
        f"{BASE_VISION}\n\n"
        f"VP-level implementation workstream: {workstream['title']}.\n"
        f"Focus: {workstream['focus']}.\n\n"
        "Return implementation-ready guidance: manifests, interfaces, deterministic validation gates, "
        "fallback triggers, receipts, demo evidence, rollout risks, and acceptance criteria. Keep the "
        "output aligned with existing Cento Hard ProReq, Workset, Factory, and Safe Integrator contracts."
    )


def image_task(workstream: dict[str, str]) -> str:
    return (
        "Create a ChatGPT image prompt for a dense Cento operator UI screenshot. "
        f"Subject: {workstream['image']}. The UI must show requirements splitting, 10 worker lanes, "
        "2-3 integrator/validator lanes, deterministic gates, AI fallback only when needed, cost/timing "
        "counters, quarantine/release evidence, and final handoff."
    )


def pipeline_payload(operator_prompt: str, reference_screenshot: str = "") -> dict[str, Any]:
    screenshot_input: dict[str, Any] = {"id": "ui-screenshot-request", "kind": "image", "source": "auto"}
    if reference_screenshot:
        screenshot_input["image_refs"] = [reference_screenshot]
        screenshot_input["image_notes"] = "Use this as visual style context for the requested parallel delivery UI image."
    return {
        "schema_version": app.PIPELINE_RUN_SCHEMA_VERSION,
        "project_id": app.HARD_PROREQ_PROJECT_ID,
        "template_id": app.HARD_PROREQ_TEMPLATE_ID,
        "inputs": [
            {"id": "operator-thoughts", "kind": "questionnaire", "source": "user", "answer": operator_prompt},
            {"id": "generated-cento-context", "kind": "path", "source": "auto"},
            screenshot_input,
            {"id": "pro-backend-schema", "kind": "details", "source": "auto"},
            {"id": "backend-work-handoff", "kind": "evidence", "source": "auto"},
        ],
    }


def pipeline_run_payload(run_id: str) -> dict[str, Any]:
    run_path = PIPELINE_ROOT / "execution" / "runs" / f"{run_id}.json"
    return read_json(run_path) or app.dev_pipeline_artifact_json(app.DEV_PIPELINE_STUDIO_ROOT, "execution/execution_run.json")


def hard_proreq_root(run_id: str) -> Path:
    return PIPELINE_ROOT / "execution" / "hard-proreq" / run_id


def summarize_hard_proreq(run_id: str) -> dict[str, Any]:
    root = hard_proreq_root(run_id)
    backend = read_json(root / "backend_work_manifest.json")
    pro_response = read_json(root / "pro_backend_response.json")
    image_response = read_json(root / "image_generation_response.json")
    image_request = read_json(root / "image_generation_request.json")
    story_index = read_json(root / "story_index.json")
    image_error = ""
    if isinstance(image_response.get("response"), dict):
        error_payload = image_response["response"].get("error")
        if isinstance(error_payload, dict):
            image_error = str(error_payload.get("message") or "")
    return {
        "artifact_root": rel(root),
        "story_count": int(backend.get("story_count") or story_index.get("story_count") or 0),
        "story_index": str(backend.get("story_index") or ""),
        "parallel_patch_workset": str(backend.get("parallel_patch_workset") or ""),
        "integration_policy": str(backend.get("integration_policy") or ""),
        "integration_plan": rel(root / "integration_plan.json"),
        "validation_plan": rel(root / "validation_plan.json"),
        "pro_backend_request": rel(root / "pro_backend_request.json"),
        "pro_response_status": str(pro_response.get("status") or ""),
        "pro_skip_code": str(pro_response.get("skip_code") or ""),
        "pro_model": str(pro_response.get("model") or ""),
        "image_request": rel(root / "image_generation_request.json"),
        "image_model": str(image_response.get("model") or image_request.get("model") or ""),
        "image_response_status": str(image_response.get("status") or ""),
        "image_skip_code": str(image_response.get("skip_code") or ""),
        "image_error": image_error,
        "generated_image": str(image_response.get("output_image") or ""),
        "evidence": rel(root / "hard_proreq_evidence.json"),
    }


def wait_for_pipeline(run_id: str, timeout_seconds: int, poll_seconds: float) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        payload = pipeline_run_payload(run_id)
        status = str(payload.get("status") or "")
        if status in {"completed", "failed", "blocked", "rejected"}:
            return payload
        time.sleep(poll_seconds)
    payload = pipeline_run_payload(run_id)
    payload["observed_status"] = str(payload.get("status") or "")
    payload["status"] = "timeout"
    payload["timeout_seconds"] = timeout_seconds
    return payload


def run_workset_check(workset_path: str, *, runtime: str = "", allow_creates: bool = False) -> dict[str, Any]:
    if not workset_path:
        return {"status": "missing", "exit_code": 1, "stdout": "", "stderr": "missing workset path"}
    command = ["./scripts/cento.sh", "workset", "check", workset_path]
    if runtime:
        command.extend(["--runtime", runtime])
    if allow_creates:
        command.append("--allow-creates")
    result = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return {
        "status": "passed" if result.returncode == 0 else "failed",
        "command": command,
        "exit_code": result.returncode,
        "stdout": result.stdout[-4000:],
        "stderr": result.stderr[-4000:],
    }


def train_latest_run_dir() -> Path | None:
    if not TRAIN_RUNS_ROOT.exists():
        return None
    candidates = [path for path in TRAIN_RUNS_ROOT.iterdir() if path.is_dir() and (path / "train_manifest.json").exists()]
    return max(candidates, key=lambda path: path.stat().st_mtime) if candidates else None


def resolve_train_run_dir(value: str | None, *, create: bool = False) -> Path:
    if value:
        path = Path(value)
        if not path.is_absolute() and ("/" not in value and "\\" not in value):
            path = TRAIN_RUNS_ROOT / value
        elif not path.is_absolute():
            path = ROOT / path
    else:
        path = TRAIN_RUNS_ROOT / now_stamp() if create else train_latest_run_dir()
        if path is None:
            path = TRAIN_RUNS_ROOT / now_stamp()
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def train_event(run_dir: Path, event: str, payload: dict[str, Any]) -> None:
    append_jsonl(run_dir / "events.ndjson", {"written_at": now_iso(), "event": event, **payload})


def text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def train_normalize_path(value: str) -> str:
    return str(value).strip().strip("/")


def train_paths_conflict(left: str, right: str) -> bool:
    left_norm = train_normalize_path(left)
    right_norm = train_normalize_path(right)
    if not left_norm or not right_norm:
        return False
    return left_norm == right_norm or left_norm.startswith(right_norm + "/") or right_norm.startswith(left_norm + "/")


def train_task_id(task: dict[str, Any], index: int) -> str:
    return str(task.get("id") or task.get("worker_id") or f"task-{index:02d}")


def train_path_blockers(tasks: list[dict[str, Any]]) -> dict[str, list[str]]:
    blockers: dict[str, list[str]] = {}
    path_owner: list[tuple[str, str]] = []
    for index, task in enumerate(tasks, start=1):
        task_id = train_task_id(task, index)
        write_paths = text_list(task.get("write_paths"))
        if not write_paths:
            blockers.setdefault(task_id, []).append("missing write_paths")
        for path in write_paths:
            if Path(path).is_absolute():
                blockers.setdefault(task_id, []).append(f"absolute write path is not allowed: {path}")
            if "*" in path or "?" in path or "[" in path:
                blockers.setdefault(task_id, []).append(f"glob write path is not allowed: {path}")
            for other_task_id, other_path in path_owner:
                if train_paths_conflict(path, other_path):
                    blockers.setdefault(task_id, []).append(f"write path conflicts with {other_task_id}: {path}")
                    blockers.setdefault(other_task_id, []).append(f"write path conflicts with {task_id}: {other_path}")
            path_owner.append((task_id, path))
    return blockers


def train_dependency_order(tasks: list[dict[str, Any]]) -> tuple[list[str], dict[str, list[str]]]:
    ids = [train_task_id(task, index) for index, task in enumerate(tasks, start=1)]
    known = set(ids)
    deps = {
        task_id: [dep for dep in text_list(task.get("depends_on")) if dep]
        for task_id, task in zip(ids, tasks)
    }
    blockers: dict[str, list[str]] = {}
    for task_id, dep_ids in deps.items():
        missing = [dep for dep in dep_ids if dep not in known]
        if missing:
            blockers.setdefault(task_id, []).append(f"missing dependency: {', '.join(missing)}")

    remaining = list(ids)
    ordered: list[str] = []
    while remaining:
        progressed = False
        for task_id in list(remaining):
            if all(dep in ordered or dep not in known for dep in deps.get(task_id, [])):
                ordered.append(task_id)
                remaining.remove(task_id)
                progressed = True
        if not progressed:
            for task_id in remaining:
                blockers.setdefault(task_id, []).append("dependency cycle or unresolved dependency")
            ordered.extend(remaining)
            break
    return ordered, blockers


def build_train_artifacts(source_workset: Path, run_dir: Path, *, max_parallel: int) -> dict[str, Any]:
    source_payload = read_json(source_workset)
    copied_workset = dict(source_payload)
    copied_workset.setdefault("max_parallel", max_parallel)
    workset_path = run_dir / "workset.json"
    write_json(workset_path, copied_workset)
    check = run_workset_check(rel(workset_path))
    tasks = [item for item in copied_workset.get("tasks") or [] if isinstance(item, dict)]
    path_blockers = train_path_blockers(tasks)
    order, dependency_blockers = train_dependency_order(tasks)
    blockers: dict[str, list[str]] = {}
    for source in (path_blockers, dependency_blockers):
        for task_id, reasons in source.items():
            blockers.setdefault(task_id, []).extend(reasons)
    deps = {train_task_id(task, index): text_list(task.get("depends_on")) for index, task in enumerate(tasks, start=1)}
    changed = True
    while changed:
        changed = False
        blocked_ids = {task_id for task_id, reasons in blockers.items() if reasons}
        for task_id, dep_ids in deps.items():
            for dep_id in dep_ids:
                if dep_id in blocked_ids:
                    reason = f"blocked dependency: {dep_id}"
                    reasons = blockers.setdefault(task_id, [])
                    if reason not in reasons:
                        reasons.append(reason)
                        changed = True

    shards: list[dict[str, Any]] = []
    for index, task in enumerate(tasks, start=1):
        task_id = train_task_id(task, index)
        reasons = sorted(set(blockers.get(task_id) or []))
        if check.get("status") != "passed" and not reasons:
            reasons = ["workset check failed"]
        shards.append(
            {
                "task_id": task_id,
                "worker_id": str(task.get("worker_id") or task_id),
                "write_paths": text_list(task.get("write_paths")),
                "depends_on": text_list(task.get("depends_on")),
                "status": "blocked" if reasons else "planned",
                "blockers": reasons,
                "integration_order": order.index(task_id) + 1 if task_id in order else index,
            }
        )
    shards_by_id = {str(item["task_id"]): item for item in shards}
    queue_items = []
    for task_id in order:
        shard = shards_by_id.get(task_id)
        if not shard:
            continue
        queue_items.append(
            {
                "task_id": task_id,
                "worker_id": shard["worker_id"],
                "write_paths": shard["write_paths"],
                "depends_on": shard["depends_on"],
                "integration_order": shard["integration_order"],
                "status": "blocked" if shard["status"] == "blocked" else ("waiting" if shard["depends_on"] else "ready_for_worker"),
                "blockers": shard["blockers"],
                "apply": False,
            }
        )
    status = "blocked" if check.get("status") != "passed" or any(item["status"] == "blocked" for item in shards) else "planned"
    manifest = {
        "schema_version": SCHEMA_TRAIN,
        "id": run_dir.name,
        "created_at": now_iso(),
        "mode": "dry-run",
        "status": status,
        "max_parallel": max_parallel,
        "source_workset": rel(source_workset),
        "workset": rel(workset_path),
        "workset_check": rel(run_dir / "workset_check.json"),
        "shards": shards,
        "integration_policy": {"strategy": "sequential", "apply": False, "validate_each": True},
        "artifacts": {
            "integration_queue": rel(run_dir / "integration_queue.json"),
            "receipt": rel(run_dir / "train_receipt.json"),
            "events": rel(run_dir / "events.ndjson"),
            "decision_report": rel(run_dir / "decision_report.md"),
        },
    }
    queue = {
        "schema_version": SCHEMA_TRAIN_QUEUE,
        "run_id": run_dir.name,
        "written_at": now_iso(),
        "strategy": "sequential",
        "apply": False,
        "items": queue_items,
    }
    write_json(run_dir / "workset_check.json", check)
    write_json(run_dir / "train_manifest.json", manifest)
    write_json(run_dir / "integration_queue.json", queue)
    write_train_report(run_dir, manifest, queue, None)
    train_event(run_dir, "train_planned", {"status": status, "task_count": len(tasks), "max_parallel": max_parallel})
    return manifest


def train_receipt_payload(run_dir: Path, manifest: dict[str, Any], queue: dict[str, Any], *, status: str) -> dict[str, Any]:
    items = queue.get("items") if isinstance(queue.get("items"), list) else []
    counts = {}
    for item in items:
        item_status = str(item.get("status") or "unknown")
        counts[item_status] = counts.get(item_status, 0) + 1
    return {
        "schema_version": SCHEMA_TRAIN_RECEIPT,
        "run_id": run_dir.name,
        "written_at": now_iso(),
        "status": status,
        "mode": "dry-run",
        "max_parallel": manifest.get("max_parallel"),
        "apply": False,
        "task_status_counts": dict(sorted(counts.items())),
        "train_manifest": rel(run_dir / "train_manifest.json"),
        "integration_queue": rel(run_dir / "integration_queue.json"),
    }


def train_workset_execute_command(
    manifest: dict[str, Any],
    *,
    runtime: str,
    runtime_profile: str = "",
    api_profile: str = "",
    api_config: str = "",
    budget_usd: float | None = None,
    max_budget_usd: float | None = None,
    validation: str = "",
    worker_timeout: int | None = None,
    retry_attempts: int | None = None,
    fixture_case: str = "valid",
    allow_dirty_owned: bool = False,
    allow_creates: bool = False,
) -> list[str]:
    workset_path = str(manifest.get("workset") or "")
    if not workset_path:
        raise ValueError("train manifest is missing workset path")
    effective_runtime = runtime or "fixture"
    if effective_runtime == "api-openai" and (budget_usd is None or max_budget_usd is None):
        raise ValueError("train workset api-openai execution requires --budget-usd and --max-budget-usd")
    command = [
        "./scripts/cento.sh",
        "workset",
        "execute",
        workset_path,
        "--max-parallel",
        str(int(manifest.get("max_parallel") or 1)),
        "--runtime",
        effective_runtime,
        "--integrate",
        "sequential",
    ]
    if runtime_profile:
        command.extend(["--runtime-profile", runtime_profile])
    if validation:
        command.extend(["--validation", validation])
    if worker_timeout is not None and worker_timeout > 0:
        command.extend(["--worker-timeout", str(worker_timeout)])
    if retry_attempts is not None and retry_attempts >= 0:
        command.extend(["--retry-attempts", str(retry_attempts)])
    if effective_runtime == "fixture":
        command.extend(["--fixture-case", fixture_case or "valid"])
    if effective_runtime == "api-openai":
        if api_profile:
            command.extend(["--api-profile", api_profile])
        if api_config:
            command.extend(["--api-config", api_config])
        command.extend(["--budget-usd", f"{float(budget_usd):.6f}", "--max-budget-usd", f"{float(max_budget_usd):.6f}"])
    if allow_dirty_owned:
        command.append("--allow-dirty-owned")
    if allow_creates:
        command.append("--allow-creates")
    command.append("--json")
    return command


def execute_train_workset(
    run_dir: Path,
    *,
    runtime: str = "fixture",
    runtime_profile: str = "",
    api_profile: str = "",
    api_config: str = "",
    budget_usd: float | None = None,
    max_budget_usd: float | None = None,
    validation: str = "smoke",
    worker_timeout: int | None = None,
    retry_attempts: int | None = None,
    fixture_case: str = "valid",
    allow_dirty_owned: bool = False,
    allow_creates: bool = False,
) -> dict[str, Any]:
    manifest = read_json(run_dir / "train_manifest.json")
    queue = read_json(run_dir / "integration_queue.json")
    items = queue.get("items") if isinstance(queue.get("items"), list) else []
    blocked = [str(item.get("task_id") or "") for item in items if item.get("status") == "blocked"]
    if blocked:
        receipt = train_receipt_payload(run_dir, manifest, queue, status="blocked")
        receipt.update(
            {
                "workset_pipeline": True,
                "workset_skipped": True,
                "errors": [f"blocked train queue items: {', '.join(sorted(blocked))}"],
            }
        )
        write_json(run_dir / "train_receipt.json", receipt)
        write_train_report(run_dir, manifest, queue, receipt)
        train_event(run_dir, "train_workset_skipped", {"status": "blocked", "blocked_items": sorted(blocked)})
        return receipt

    try:
        command = train_workset_execute_command(
            manifest,
            runtime=runtime,
            runtime_profile=runtime_profile,
            api_profile=api_profile,
            api_config=api_config,
            budget_usd=budget_usd,
            max_budget_usd=max_budget_usd,
            validation=validation,
            worker_timeout=worker_timeout,
            retry_attempts=retry_attempts,
            fixture_case=fixture_case,
            allow_dirty_owned=allow_dirty_owned,
            allow_creates=allow_creates,
        )
    except ValueError as exc:
        receipt = train_receipt_payload(run_dir, manifest, queue, status="workset_rejected")
        receipt.update({"workset_pipeline": True, "errors": [str(exc)]})
        write_json(run_dir / "train_receipt.json", receipt)
        write_train_report(run_dir, manifest, queue, receipt)
        train_event(run_dir, "train_workset_rejected", {"error": str(exc)})
        return receipt

    command_record = {
        "schema_version": "cento.parallel_integration_train.workset_execute_command.v1",
        "run_id": run_dir.name,
        "written_at": now_iso(),
        "command": command,
        "runtime": runtime or "fixture",
        "apply": False,
        "integration": "sequential",
    }
    write_json(run_dir / "workset_execute_command.json", command_record)
    train_event(run_dir, "train_workset_execute_started", {"runtime": runtime or "fixture", "command": " ".join(shlex.quote(part) for part in command)})

    result = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    try:
        workset_result = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        workset_result = {}
    write_json(
        run_dir / "workset_execute_result.json",
        {
            "schema_version": "cento.parallel_integration_train.workset_execute_result.v1",
            "run_id": run_dir.name,
            "written_at": now_iso(),
            "exit_code": result.returncode,
            "stdout": result.stdout[-4000:],
            "stderr": result.stderr[-4000:],
            "payload": workset_result,
        },
    )

    task_statuses = workset_result.get("task_statuses") if isinstance(workset_result.get("task_statuses"), dict) else {}
    success_statuses = {"accepted", "applied", "completed"}
    for item in items:
        if item.get("status") == "blocked":
            continue
        task_id = str(item.get("task_id") or "")
        task_status = str(task_statuses.get(task_id) or "")
        item["workset_task_status"] = task_status or "missing"
        item["workset_receipt"] = str(workset_result.get("workset_receipt") or "")
        item["workset_dir"] = str(workset_result.get("workset_dir") or "")
        if task_status in success_statuses:
            item["status"] = "workset_integrated"
        elif task_status:
            item["status"] = "blocked"
            reason = f"workset task status: {task_status}"
            blockers = item.setdefault("blockers", [])
            if reason not in blockers:
                blockers.append(reason)
        else:
            item["status"] = "blocked"
            blockers = item.setdefault("blockers", [])
            if "workset task status missing" not in blockers:
                blockers.append("workset task status missing")

    queue["written_at"] = now_iso()
    queue["workset_pipeline"] = True
    queue["workset_execute_result"] = rel(run_dir / "workset_execute_result.json")
    write_json(run_dir / "integration_queue.json", queue)
    status = "workset_completed" if result.returncode == 0 and workset_result.get("status") == "completed" and all(item.get("status") == "workset_integrated" for item in items) else "workset_failed"
    receipt = train_receipt_payload(run_dir, manifest, queue, status=status)
    receipt.update(
        {
            "workset_pipeline": True,
            "workset_runtime": runtime or "fixture",
            "workset_status": str(workset_result.get("status") or ""),
            "workset_exit_code": result.returncode,
            "workset_dir": str(workset_result.get("workset_dir") or ""),
            "workset_receipt": str(workset_result.get("workset_receipt") or ""),
            "workset_total_cost_usd": workset_result.get("total_cost_usd", 0.0),
            "workset_execute_command": rel(run_dir / "workset_execute_command.json"),
            "workset_execute_result": rel(run_dir / "workset_execute_result.json"),
            "stdout": result.stdout[-4000:],
            "stderr": result.stderr[-4000:],
        }
    )
    write_json(run_dir / "train_receipt.json", receipt)
    write_train_report(run_dir, manifest, queue, receipt)
    train_event(
        run_dir,
        "train_workset_execute_completed",
        {"status": status, "exit_code": result.returncode, "workset_status": str(workset_result.get("status") or "")},
    )
    return receipt


def resolve_cento_path(value: str | Path) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else ROOT / path


def train_factory_run_dir(run_dir: Path) -> Path:
    return FACTORY_RUNS_ROOT / f"parallel-train-{run_dir.name}"


def workset_receipt_payload(receipt: dict[str, Any]) -> tuple[Path | None, dict[str, Any]]:
    value = str(receipt.get("workset_receipt") or "")
    if not value:
        return None, {}
    path = resolve_cento_path(value)
    return path, read_json(path)


def workset_task_lookup(workset_receipt: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = workset_receipt.get("tasks") if isinstance(workset_receipt.get("tasks"), dict) else {}
    return {str(task_id): task for task_id, task in raw.items() if isinstance(task, dict)}


def train_factory_plan_payload(run_dir: Path, factory_run_dir: Path, queue: dict[str, Any], workset_receipt: dict[str, Any]) -> dict[str, Any]:
    manifest = read_json(run_dir / "train_manifest.json")
    workset = read_json(resolve_cento_path(str(manifest.get("workset") or "")))
    source_tasks = {
        train_task_id(task, index): task
        for index, task in enumerate([item for item in workset.get("tasks") or [] if isinstance(item, dict)], start=1)
    }
    items = sorted(queue.get("items") if isinstance(queue.get("items"), list) else [], key=lambda item: int(item.get("integration_order") or 0))
    tasks: list[dict[str, Any]] = []
    for item in items:
        task_id = str(item.get("task_id") or "")
        source_task = source_tasks.get(task_id, {})
        write_paths = text_list(item.get("write_paths"))
        task_title = str(source_task.get("title") or source_task.get("task") or task_id)
        tasks.append(
            {
                "id": task_id,
                "title": f"Promote train task: {task_title}",
                "lane": "builder",
                "node": "linux",
                "owned_scope": write_paths,
                "goal": f"Promote accepted Workset output for train task `{task_id}` into the Factory Safe Integrator handoff.",
                "expected_outputs": [
                    {
                        "path": rel(factory_run_dir / "patches" / task_id / "patch.json"),
                        "description": "Factory-collected patch bundle converted from the Workset receipt.",
                    }
                ],
                "validation_commands": [f"python3 -m json.tool {shlex.quote(str(factory_run_dir / 'patches' / task_id / 'validation-result.json'))}"],
                "no_model_eligible": True,
                "risk": "low",
                "dependencies": text_list(item.get("depends_on")),
            }
        )
    return {
        "schema_version": "factory-plan/v1",
        "run_id": factory_run_dir.name,
        "request": {
            "raw": f"Promote parallel train run {run_dir.name} into Factory Safe Integrator.",
            "normalized_goal": "Convert accepted parallel Workset outputs into a Factory apply plan and release-candidate handoff.",
        },
        "package": "parallel-train-promotion",
        "mode": "plan_only",
        "risk": "low",
        "budget": {
            "ai_call_budget": 0,
            "estimated_cost_usd": float(workset_receipt.get("total_cost_usd") or 0.0),
            "strong_model_calls_allowed": 0,
            "cheap_worker_calls_allowed": 0,
        },
        "shared_paths": [],
        "tasks": tasks,
        "integration": {
            "strategy": "safe_integrator_from_parallel_train",
            "merge_order": [str(item.get("task_id") or "") for item in items if item.get("task_id")],
            "required_docs": [],
        },
        "validation": {
            "minimum_tier": "tier0",
            "requires_screenshots": False,
            "requires_api_smoke": False,
            "requires_human_review": True,
        },
        "evidence": {
            "run_dir": rel(factory_run_dir),
            "summary": rel(factory_run_dir / "summary.md"),
        },
        "created_at": now_iso(),
        "source_train": {
            "run_id": run_dir.name,
            "run_dir": rel(run_dir),
            "train_receipt": rel(run_dir / "train_receipt.json"),
            "workset_receipt": str(workset_receipt.get("workset_receipt") or ""),
        },
    }


def train_promotion_rows(queue: dict[str, Any], workset_receipt: dict[str, Any]) -> list[dict[str, Any]]:
    tasks = workset_task_lookup(workset_receipt)
    rows: list[dict[str, Any]] = []
    items = queue.get("items") if isinstance(queue.get("items"), list) else []
    for item in items:
        task_id = str(item.get("task_id") or "")
        task = tasks.get(task_id, {})
        reasons: list[str] = []
        if item.get("status") != "workset_integrated":
            reasons.append(f"train queue status is {item.get('status') or 'unknown'}")
        if str(task.get("status") or "") not in {"accepted", "applied", "completed"}:
            reasons.append(f"workset task status is {task.get('status') or 'missing'}")
        patch_bundle = str(task.get("patch_bundle") or "")
        if not patch_bundle or not resolve_cento_path(patch_bundle).exists():
            reasons.append("patch bundle missing")
        validation_receipt = read_json(resolve_cento_path(str(task.get("validation_receipt") or ""))) if task.get("validation_receipt") else {}
        if validation_receipt.get("status") not in {"passed", "pass", "ok"}:
            reasons.append(f"validation status is {validation_receipt.get('status') or 'missing'}")
        rows.append(
            {
                "task_id": task_id,
                "status": "accepted" if not reasons else "blocked",
                "reasons": reasons,
                "workset_task_status": task.get("status", ""),
                "patch_bundle": patch_bundle,
                "validation_receipt": str(task.get("validation_receipt") or ""),
                "changed_paths": text_list(task.get("changed_paths")),
            }
        )
    return rows


def copy_workset_outputs_to_factory(factory_run_dir: Path, queue: dict[str, Any], workset_receipt: dict[str, Any]) -> None:
    tasks = workset_task_lookup(workset_receipt)
    items = queue.get("items") if isinstance(queue.get("items"), list) else []
    for item in items:
        task_id = str(item.get("task_id") or "")
        task = tasks.get(task_id, {})
        task_dir = factory_run_dir / "tasks" / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        patch_bundle = read_json(resolve_cento_path(str(task.get("patch_bundle") or ""))) if task.get("patch_bundle") else {}
        patch_file = str(task.get("patch") or patch_bundle.get("patch_file") or "")
        if patch_file and resolve_cento_path(patch_file).exists():
            shutil.copy2(resolve_cento_path(patch_file), task_dir / "patch.diff")
        changed_files = text_list(patch_bundle.get("touched_paths")) or text_list(task.get("changed_paths"))
        (task_dir / "changed-files.txt").write_text("\n".join(changed_files) + ("\n" if changed_files else ""), encoding="utf-8")
        diffstat = "\n".join(changed_files) if changed_files else "Patch changed-files unavailable."
        (task_dir / "diffstat.txt").write_text(diffstat + "\n", encoding="utf-8")
        validation_receipt = read_json(resolve_cento_path(str(task.get("validation_receipt") or ""))) if task.get("validation_receipt") else {}
        validation_status = str(validation_receipt.get("status") or "unknown")
        write_json(
            task_dir / "validation-result.json",
            {
                "schema_version": "factory-validation-result/v1",
                "status": "passed" if validation_status in {"passed", "pass", "ok"} else validation_status,
                "source_validation_receipt": str(task.get("validation_receipt") or ""),
                "ai_calls_used": 0,
                "estimated_ai_cost_usd": 0,
                "generated_at": now_iso(),
            },
        )
        handoff = [
            f"# {task_id} Train Promotion Handoff",
            "",
            f"- Workset status: `{task.get('status') or 'unknown'}`",
            f"- Patch bundle: `{task.get('patch_bundle') or ''}`",
            f"- Validation receipt: `{task.get('validation_receipt') or ''}`",
        ]
        (task_dir / "handoff.md").write_text("\n".join(handoff) + "\n", encoding="utf-8")
        evidence_dir = task_dir / "evidence"
        evidence_dir.mkdir(exist_ok=True)
        write_json(
            evidence_dir / "workset-task.json",
            {
                "schema_version": "cento.parallel_integration_train.factory_task_evidence.v1",
                "task_id": task_id,
                "workset_task": task,
                "source_workset_receipt": str(workset_receipt.get("workset_receipt") or ""),
                "written_at": now_iso(),
            },
        )


def write_promotion_report(run_dir: Path, decision: dict[str, Any]) -> None:
    lines = [
        "# Train Promotion Decision",
        "",
        f"- Train: `{run_dir.name}`",
        f"- Status: `{decision.get('status')}`",
        f"- Decision: `{decision.get('decision')}`",
        f"- Factory run: `{decision.get('factory_run_dir') or '-'}`",
        f"- Candidates: `{decision.get('candidate_count', 0)}`",
        f"- Rejected: `{decision.get('rejected_count', 0)}`",
        "",
        "## Artifacts",
        "",
        f"- Promotion manifest: `{rel(run_dir / 'promotion_manifest.json')}`",
        f"- Factory handoff: `{rel(run_dir / 'factory_handoff.json')}`",
        f"- Promotion decision: `{rel(run_dir / 'promotion_decision.json')}`",
    ]
    if decision.get("release_candidate"):
        lines.append(f"- Release candidate: `{decision.get('release_candidate')}`")
    blockers = decision.get("blockers") if isinstance(decision.get("blockers"), list) else []
    if blockers:
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- {item}" for item in blockers)
    (run_dir / "promotion_decision.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def promote_train_run(
    run_dir: Path,
    *,
    apply: bool = False,
    validate_each: bool = False,
    branch: str = "",
    worktree: str = "",
    limit: int = 0,
) -> dict[str, Any]:
    queue = read_json(run_dir / "integration_queue.json")
    receipt = read_json(run_dir / "train_receipt.json")
    workset_receipt_path, workset_receipt = workset_receipt_payload(receipt)
    blockers: list[str] = []
    if receipt.get("status") != "workset_completed":
        blockers.append(f"train status is {receipt.get('status') or 'unknown'}")
    if not workset_receipt:
        blockers.append("workset receipt missing")
    rows = train_promotion_rows(queue, workset_receipt) if workset_receipt else []

    factory_run_dir = train_factory_run_dir(run_dir)
    promotion_manifest = {
        "schema_version": "cento.parallel_integration_train.promotion_manifest.v1",
        "run_id": run_dir.name,
        "written_at": now_iso(),
        "mode": "apply" if apply else "dry-run",
        "train_run_dir": rel(run_dir),
        "train_receipt": rel(run_dir / "train_receipt.json"),
        "workset_receipt": rel(workset_receipt_path) if workset_receipt_path else "",
        "factory_run_dir": rel(factory_run_dir),
        "tasks": rows,
    }
    write_json(run_dir / "promotion_manifest.json", promotion_manifest)

    factory_handoff: dict[str, Any] = {
        "schema_version": "cento.parallel_integration_train.factory_handoff.v1",
        "run_id": run_dir.name,
        "written_at": now_iso(),
        "factory_run_dir": rel(factory_run_dir),
        "promotion_manifest": rel(run_dir / "promotion_manifest.json"),
    }
    apply_plan: dict[str, Any] = {}
    apply_result: dict[str, Any] = {}
    integrated_validation: dict[str, Any] = {}
    release: dict[str, Any] = {}
    if not blockers:
        factory_run_dir.mkdir(parents=True, exist_ok=True)
        factory_plan = train_factory_plan_payload(run_dir, factory_run_dir, queue, workset_receipt)
        write_json(factory_run_dir / "factory-plan.json", factory_plan)
        (factory_run_dir / "summary.md").write_text(f"# Parallel Train Promotion\n\nSource train: `{run_dir.name}`\n", encoding="utf-8")
        factory_tool.materialize_run(factory_run_dir)
        factory_dispatch.generate_queue(factory_run_dir)
        copy_workset_outputs_to_factory(factory_run_dir, queue, workset_receipt)
        patch_collection = factory_dispatch.collect_patches(factory_run_dir)
        apply_plan = factory_integrator.create_apply_plan(factory_run_dir)
        factory_integrator.update_integration_state(factory_run_dir)
        factory_handoff.update(
            {
                "factory_plan": rel(factory_run_dir / "factory-plan.json"),
                "factory_queue": rel(factory_run_dir / "queue" / "queue.json"),
                "patch_collection": rel(factory_run_dir / "patch-collection-summary.json"),
                "apply_plan": rel(factory_run_dir / "integration" / "apply-plan.json"),
                "patch_collection_status": patch_collection.get("schema_version", ""),
            }
        )
        if apply:
            factory_integrator.prepare_branch(factory_run_dir, branch=branch, worktree=worktree or None)
            apply_result = factory_integrator.apply_patches(factory_run_dir, worktree=worktree or None, branch=branch, limit=limit, validate_each=validate_each)
            integrated_validation = factory_integrator.validate_integrated(factory_run_dir)
            release = factory_integrator.render_release_candidate(factory_run_dir)
            factory_handoff.update(
                {
                    "apply_result": rel(factory_run_dir / "integration" / "applied-patches.json"),
                    "integrated_validation": rel(factory_run_dir / "integration" / "integrated-validation.json"),
                    "release_candidate": release.get("release_candidate", ""),
                }
            )

    candidate_count = len(apply_plan.get("candidates") or [])
    rejected_count = len(apply_plan.get("rejected") or []) + len(blockers)
    if blockers:
        decision_value = "blocked"
        status = "blocked"
    elif apply:
        decision_value = "release_candidate_ready" if integrated_validation.get("decision") == "approve" else "apply_blocked"
        status = "completed" if decision_value == "release_candidate_ready" else "blocked"
    elif candidate_count and rejected_count == 0:
        decision_value = "ready_for_apply"
        status = "planned"
    elif candidate_count:
        decision_value = "partial_ready_for_apply"
        status = "planned"
    else:
        decision_value = "blocked"
        status = "blocked"
    decision = {
        "schema_version": "cento.parallel_integration_train.promotion_decision.v1",
        "run_id": run_dir.name,
        "written_at": now_iso(),
        "status": status,
        "decision": decision_value,
        "mode": "apply" if apply else "dry-run",
        "factory_run_dir": rel(factory_run_dir) if not blockers else "",
        "candidate_count": candidate_count,
        "rejected_count": rejected_count,
        "blockers": blockers,
        "blocked_tasks": [row for row in rows if row.get("status") != "accepted"],
        "promotion_manifest": rel(run_dir / "promotion_manifest.json"),
        "factory_handoff": rel(run_dir / "factory_handoff.json"),
        "apply_plan": rel(factory_run_dir / "integration" / "apply-plan.json") if apply_plan else "",
        "release_candidate": release.get("release_candidate", ""),
    }
    write_json(run_dir / "factory_handoff.json", factory_handoff)
    write_json(run_dir / "promotion_decision.json", decision)
    write_promotion_report(run_dir, decision)
    train_event(run_dir, "train_promoted", {"status": status, "decision": decision_value, "factory_run_dir": decision["factory_run_dir"]})
    return decision


def write_train_report(run_dir: Path, manifest: dict[str, Any], queue: dict[str, Any], receipt: dict[str, Any] | None) -> None:
    items = queue.get("items") if isinstance(queue.get("items"), list) else []
    lines = [
        "# Parallel Integration Train",
        "",
        f"- Run: `{run_dir.name}`",
        f"- Status: `{receipt.get('status') if receipt else manifest.get('status')}`",
        f"- Mode: `{manifest.get('mode')}`",
        f"- Max parallel: `{manifest.get('max_parallel')}`",
        f"- Workset: `{manifest.get('workset')}`",
        f"- Apply: `false`",
    ]
    if receipt and receipt.get("workset_pipeline"):
        lines.extend(
            [
                f"- Workset pipeline: `{receipt.get('workset_status') or 'skipped'}`",
                f"- Workset receipt: `{receipt.get('workset_receipt') or '-'}`",
            ]
        )
    lines.extend(["", "## Queue", ""])
    if items:
        for item in items:
            blockers = ", ".join(str(reason) for reason in item.get("blockers") or []) or "-"
            lines.append(f"- `{item.get('status')}` order={item.get('integration_order')} task=`{item.get('task_id')}` worker=`{item.get('worker_id')}` blockers={blockers}")
    else:
        lines.append("- No queue items.")
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            f"- Manifest: `{rel(run_dir / 'train_manifest.json')}`",
            f"- Queue: `{rel(run_dir / 'integration_queue.json')}`",
            f"- Receipt: `{rel(run_dir / 'train_receipt.json')}`",
            f"- Events: `{rel(run_dir / 'events.ndjson')}`",
        ]
    )
    if (run_dir / "workset_execute_command.json").exists():
        lines.append(f"- Workset execute command: `{rel(run_dir / 'workset_execute_command.json')}`")
    if (run_dir / "workset_execute_result.json").exists():
        lines.append(f"- Workset execute result: `{rel(run_dir / 'workset_execute_result.json')}`")
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "- Worker readiness can be simulated or delegated to `cento workset execute`.",
            "- Integration remains sequential and dry-run by default.",
            "- Train workset execution does not pass `--apply`.",
            "",
        ]
    )
    (run_dir / "decision_report.md").write_text("\n".join(lines), encoding="utf-8")


def simulate_train_workers(run_dir: Path) -> dict[str, Any]:
    manifest = read_json(run_dir / "train_manifest.json")
    queue = read_json(run_dir / "integration_queue.json")
    items = queue.get("items") if isinstance(queue.get("items"), list) else []
    for item in items:
        if item.get("status") == "blocked":
            continue
        item["status"] = "ready_for_integration"
        worker_dir = run_dir / "workers" / str(item.get("worker_id") or item.get("task_id"))
        write_json(
            worker_dir / "worker_receipt.json",
            {
                "schema_version": "cento.parallel_integration_train.worker_receipt.v1",
                "run_id": run_dir.name,
                "task_id": item.get("task_id"),
                "worker_id": item.get("worker_id"),
                "status": "simulated_ready",
                "apply": False,
                "written_at": now_iso(),
            },
        )
    queue["written_at"] = now_iso()
    write_json(run_dir / "integration_queue.json", queue)
    status = "blocked" if any(item.get("status") == "blocked" for item in items) else "workers_simulated"
    receipt = train_receipt_payload(run_dir, manifest, queue, status=status)
    write_json(run_dir / "train_receipt.json", receipt)
    write_train_report(run_dir, manifest, queue, receipt)
    train_event(run_dir, "train_workers_simulated", {"status": status})
    return receipt


def dry_run_train_integration(run_dir: Path) -> dict[str, Any]:
    manifest = read_json(run_dir / "train_manifest.json")
    queue = read_json(run_dir / "integration_queue.json")
    items = queue.get("items") if isinstance(queue.get("items"), list) else []
    for item in items:
        if item.get("status") == "ready_for_integration":
            item["status"] = "integration_planned"
            integration_dir = run_dir / "integration" / str(item.get("task_id"))
            write_json(
                integration_dir / "integration_receipt.json",
                {
                    "schema_version": "cento.parallel_integration_train.integration_receipt.v1",
                    "run_id": run_dir.name,
                    "task_id": item.get("task_id"),
                    "status": "dry_run_planned",
                    "apply": False,
                    "written_at": now_iso(),
                },
            )
        elif item.get("status") in {"ready_for_worker", "waiting"}:
            item["status"] = "waiting_for_worker_simulation"
    queue["written_at"] = now_iso()
    write_json(run_dir / "integration_queue.json", queue)
    status = "blocked" if any(item.get("status") == "blocked" for item in items) else "integration_planned"
    receipt = train_receipt_payload(run_dir, manifest, queue, status=status)
    write_json(run_dir / "train_receipt.json", receipt)
    write_train_report(run_dir, manifest, queue, receipt)
    train_event(run_dir, "train_integration_dry_run", {"status": status})
    return receipt


def validate_train_run(run_dir: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, detail: str = "") -> None:
        checks.append({"name": name, "status": "passed" if passed else "failed", "detail": detail})

    manifest = read_json(run_dir / "train_manifest.json")
    queue = read_json(run_dir / "integration_queue.json")
    check = read_json(run_dir / "workset_check.json")
    receipt = read_json(run_dir / "train_receipt.json")
    add("manifest.schema", manifest.get("schema_version") == SCHEMA_TRAIN)
    add("queue.schema", queue.get("schema_version") == SCHEMA_TRAIN_QUEUE)
    add("workset_check.passed", check.get("status") == "passed", str(check.get("stderr") or ""))
    add("receipt.schema", receipt.get("schema_version") == SCHEMA_TRAIN_RECEIPT)
    add("decision_report.exists", (run_dir / "decision_report.md").exists())
    items = queue.get("items") if isinstance(queue.get("items"), list) else []
    add("queue.non_empty", bool(items), f"{len(items)} items")
    add("apply.disabled", manifest.get("integration_policy", {}).get("apply") is False and receipt.get("apply") is False)
    if receipt.get("workset_pipeline"):
        workset_result = read_json(run_dir / "workset_execute_result.json")
        add("workset_execute_result.exists", bool(workset_result))
        add("workset_execute.completed", receipt.get("status") == "workset_completed" and receipt.get("workset_status") == "completed", str(receipt.get("workset_status") or ""))
        add("workset_receipt.present", bool(receipt.get("workset_receipt")))
    promotion = read_json(run_dir / "promotion_decision.json")
    if promotion:
        promotion_manifest = read_json(run_dir / "promotion_manifest.json")
        factory_handoff = read_json(run_dir / "factory_handoff.json")
        add("promotion.schema", promotion.get("schema_version") == "cento.parallel_integration_train.promotion_decision.v1")
        add("promotion_manifest.schema", promotion_manifest.get("schema_version") == "cento.parallel_integration_train.promotion_manifest.v1")
        add("factory_handoff.schema", factory_handoff.get("schema_version") == "cento.parallel_integration_train.factory_handoff.v1")
        add("promotion_report.exists", (run_dir / "promotion_decision.md").exists())
    status = "passed" if all(item["status"] == "passed" for item in checks) else "failed"
    payload = {"schema_version": "cento.parallel_integration_train.validation.v1", "run_id": run_dir.name, "written_at": now_iso(), "status": status, "checks": checks}
    write_json(run_dir / "validation_summary.json", payload)
    return payload


def patch_swarm_latest_run_dir() -> Path | None:
    if not PATCH_SWARM_RUNS_ROOT.exists():
        return None
    candidates = [path for path in PATCH_SWARM_RUNS_ROOT.iterdir() if path.is_dir() and (path / "patch_swarm_manifest.json").exists()]
    return max(candidates, key=lambda path: path.stat().st_mtime) if candidates else None


def resolve_patch_swarm_run_dir(value: str | None, *, create: bool = False) -> Path:
    if value:
        path = Path(value)
        if not path.is_absolute() and ("/" not in value and "\\" not in value):
            path = PATCH_SWARM_RUNS_ROOT / value
        elif not path.is_absolute():
            path = ROOT / path
    else:
        path = PATCH_SWARM_RUNS_ROOT / f"patch-swarm-{now_stamp()}" if create else patch_swarm_latest_run_dir()
        if path is None:
            path = PATCH_SWARM_RUNS_ROOT / f"patch-swarm-{now_stamp()}"
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def patch_swarm_event(run_dir: Path, event: str, payload: dict[str, Any]) -> None:
    append_jsonl(run_dir / "events.ndjson", {"written_at": now_iso(), "event": event, **payload})


def patch_swarm_provider_list(value: str | list[str] | None = None) -> list[str]:
    raw_items: list[str]
    if isinstance(value, list):
        raw_items = [str(item) for item in value]
    else:
        raw_items = [item.strip() for item in str(value or "").split(",")]
    providers: list[str] = []
    for item in raw_items:
        if not item:
            continue
        normalized = PATCH_SWARM_PROVIDER_ALIASES.get(item.strip().lower().replace(" ", "-"))
        if normalized and normalized not in providers:
            providers.append(normalized)
    return providers or list(PATCH_SWARM_PROVIDERS)


def patch_swarm_api_candidate_count(candidate_target: int, providers: list[str]) -> int:
    providers = providers or list(PATCH_SWARM_PROVIDERS)
    distribution = patch_swarm_candidate_distribution(candidate_target, len(PATCH_SWARM_PROREQ_EXECUTIONS))
    total = 0
    global_index = 0
    for candidate_count in distribution:
        for _ in range(candidate_count):
            global_index += 1
            provider = providers[(global_index - 1) % len(providers)]
            if provider == "api-openai":
                total += 1
    return total


def patch_swarm_estimated_cost(candidate_target: int, providers: list[str], api_sandbox_candidates: int | None = None) -> float:
    api_candidate_count = patch_swarm_api_candidate_count(candidate_target, providers)
    if api_sandbox_candidates is not None:
        api_candidate_count = min(api_candidate_count, max(0, int(api_sandbox_candidates)))
    total = api_candidate_count * PATCH_SWARM_API_COST_ESTIMATE_USD
    return round(total, 6)


def patch_swarm_budget_gate(
    run_dir: Path,
    *,
    budget_cap_usd: float | None,
    max_budget_usd: float | None = None,
    api_sandbox_candidates: int | None = None,
) -> dict[str, Any]:
    manifest = read_json(run_dir / "patch_swarm_manifest.json")
    providers = patch_swarm_provider_list(manifest.get("providers") if isinstance(manifest.get("providers"), list) else "")
    candidate_target = int(manifest.get("candidate_target") or 0)
    api_candidate_count = patch_swarm_api_candidate_count(candidate_target, providers)
    metered_api_candidates = min(api_candidate_count, max(0, int(api_sandbox_candidates))) if api_sandbox_candidates is not None else api_candidate_count
    estimated = patch_swarm_estimated_cost(candidate_target, providers, api_sandbox_candidates)
    cap = float(budget_cap_usd or 0.0)
    hard_cap = float(max_budget_usd if max_budget_usd is not None else PATCH_SWARM_DEFAULT_LIVE_HARD_CAP_USD)
    blockers: list[str] = []
    if cap <= 0:
        blockers.append("live execution requires --budget-cap-usd")
    if hard_cap <= 0:
        blockers.append("hard budget cap must be positive")
    if cap > hard_cap:
        blockers.append("budget cap exceeds hard budget cap")
    if hard_cap > PATCH_SWARM_DEFAULT_LIVE_HARD_CAP_USD:
        blockers.append(f"hard budget cap exceeds ${PATCH_SWARM_DEFAULT_LIVE_HARD_CAP_USD:.2f} rollout ceiling")
    if estimated > cap:
        blockers.append("estimated provider spend exceeds budget cap")
    if "api-openai" in providers and metered_api_candidates > 0 and not os.environ.get("OPENAI_API_KEY"):
        blockers.append("OPENAI_API_KEY is missing")
    gate = {
        "schema_version": "cento.patch_swarm.live_budget_gate.v1",
        "run_id": run_dir.name,
        "status": "passed" if not blockers else "blocked",
        "budget_cap_usd": cap,
        "hard_budget_cap_usd": hard_cap,
        "estimated_cost_usd": estimated,
        "providers": providers,
        "candidate_target": candidate_target,
        "api_candidate_count": api_candidate_count,
        "metered_api_candidate_limit": metered_api_candidates,
        "blockers": blockers,
        "written_at": now_iso(),
    }
    write_json(run_dir / "usage_guard.json", gate)
    return gate


def patch_swarm_candidate_errors(candidate: dict[str, Any], run_dir: Path | None = None) -> list[str]:
    errors: list[str] = []
    if candidate.get("schema_version") != SCHEMA_PATCH_SWARM_CANDIDATE:
        errors.append("schema_version must be candidate_patch.v1")
    for field in ("id", "run_id", "execution_id", "provider", "status", "touched_paths", "patch"):
        if field not in candidate:
            errors.append(f"missing field: {field}")
    provider = str(candidate.get("provider") or "")
    if provider not in PATCH_SWARM_PROVIDERS:
        errors.append(f"unknown provider: {provider}")
    touched_paths = candidate.get("touched_paths")
    if not isinstance(touched_paths, list) or not all(isinstance(item, str) and item for item in touched_paths):
        errors.append("touched_paths must be a non-empty list of strings")
    patch = candidate.get("patch") if isinstance(candidate.get("patch"), dict) else {}
    patch_file = str(patch.get("patch_file") or "")
    if not patch_file:
        errors.append("patch.patch_file is required")
    elif run_dir is not None:
        resolved = resolve_cento_path(patch_file)
        if not resolved.exists():
            errors.append("patch.patch_file does not exist")
        expected = str(patch.get("sha256") or "")
        actual = hashlib.sha256(resolved.read_bytes()).hexdigest() if resolved.exists() else ""
        if expected and actual and expected != actual:
            errors.append("patch.sha256 mismatch")
    if float(candidate.get("cost_usd_estimate") or 0.0) < 0:
        errors.append("cost_usd_estimate must be non-negative")
    if str(candidate.get("status") or "") not in {"validated", "rejected", "proposed", "blocked"}:
        errors.append("status must be validated, rejected, proposed, or blocked")
    return errors


def patch_swarm_selected_repo_root(run_dir: Path) -> Path:
    metadata = read_json(run_dir / "product_metadata.json")
    manifest = read_json(run_dir / "patch_swarm_manifest.json")
    selected_repo = metadata.get("selected_repo") if isinstance(metadata.get("selected_repo"), dict) else {}
    if not selected_repo:
        selected_repo = manifest.get("selected_repo") if isinstance(manifest.get("selected_repo"), dict) else {}
    raw_path = str(selected_repo.get("path") or selected_repo.get("root") or "").strip()
    if not raw_path:
        return ROOT
    repo_root = Path(raw_path).expanduser()
    if not repo_root.is_absolute():
        repo_root = ROOT / repo_root
    return repo_root if repo_root.exists() and repo_root.is_dir() else ROOT


def append_patch_swarm_usage(run_dir: Path, candidate: dict[str, Any]) -> None:
    provider = str(candidate.get("provider") or "unknown")
    row = {
        "written_at": now_iso(),
        "run_id": run_dir.name,
        "candidate_id": str(candidate.get("id") or ""),
        "execution_id": str(candidate.get("execution_id") or ""),
        "provider": provider,
        "cost_usd_estimate": float(candidate.get("cost_usd_estimate") or 0.0),
        "duration_ms_estimate": float(candidate.get("duration_ms_estimate") or 0.0),
    }
    append_jsonl(run_dir / "provider_usage.jsonl", row)
    append_jsonl(run_dir / "candidate_spend_ledger.jsonl", row)


def patch_swarm_slug(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in str(value)).strip("-") or "patch-swarm"


def patch_swarm_candidate_distribution(candidate_target: int, execution_count: int) -> list[int]:
    candidate_target = max(1, int(candidate_target))
    execution_count = max(1, int(execution_count))
    base = candidate_target // execution_count
    remainder = candidate_target % execution_count
    return [base + (1 if index < remainder else 0) for index in range(execution_count)]


def patch_swarm_prompt_text(objective: str, execution: dict[str, Any], providers: list[str], candidate_count: int) -> str:
    provider_lines = [
        f"- {provider}: {PATCH_SWARM_PROVIDER_RUNTIMES.get(provider, {}).get('runtime_profile') or PATCH_SWARM_PROVIDER_RUNTIMES.get(provider, {}).get('output_schema')}"
        for provider in providers
    ]
    return "\n".join(
        [
            f"# Patch Swarm ProReq Execution: {execution['title']}",
            "",
            f"Objective: {objective}",
            "",
            f"Focus: {execution['focus']}",
            "",
            f"Generate {candidate_count} candidate patch proposal(s).",
            "",
            "Allowed providers:",
            *provider_lines,
            "",
            "Rules:",
            "- Emit candidate_patch.v1 receipts.",
            "- Do not mutate the operator worktree.",
            "- Command runtimes must use isolated worktrees.",
            "- API workers must return structured patch_proposal.v1 artifacts.",
            "- The dedicated integrator is the only execution allowed to select winners.",
            "",
        ]
    )


def patch_swarm_cost_policy(candidate_target: int, max_parallel_agents: int, providers: list[str], live: bool) -> dict[str, Any]:
    estimated_cost_usd = patch_swarm_estimated_cost(candidate_target, providers)
    return {
        "schema_version": "cento.patch_swarm.cost_policy.v1",
        "candidate_target": candidate_target,
        "max_parallel_agents": max_parallel_agents,
        "providers": providers,
        "estimated_cost_usd": estimated_cost_usd,
        "default_live_hard_cap_usd": PATCH_SWARM_DEFAULT_LIVE_HARD_CAP_USD,
        "live_dispatch_enabled": bool(live),
        "default_mode": "fixture" if not live else "live",
        "hard_cap_required_for_live_api": True,
        "deterministic_first": True,
        "stop_conditions": [
            "hard budget cap reached",
            "duplicate saturation above threshold",
            "validator failure rate above threshold",
            "no new winning candidate after ranking pass",
        ],
    }


def patch_swarm_execution_manifest(
    run_dir: Path,
    *,
    objective: str,
    candidate_target: int,
    max_parallel_agents: int,
    providers: list[str],
    live: bool,
) -> dict[str, Any]:
    distribution = patch_swarm_candidate_distribution(candidate_target, len(PATCH_SWARM_PROREQ_EXECUTIONS))
    executions: list[dict[str, Any]] = []
    for index, (execution, candidate_count) in enumerate(zip(PATCH_SWARM_PROREQ_EXECUTIONS, distribution), start=1):
        execution_dir = run_dir / "proreq_executions" / execution["id"]
        prompt_rel = rel(execution_dir / "prompt.md")
        request_rel = rel(execution_dir / "proreq_request.json")
        executions.append(
            {
                "id": execution["id"],
                "title": execution["title"],
                "sequence": index,
                "status": "planned",
                "focus": execution["focus"],
                "owned_paths": list(execution.get("owned_paths") or []),
                "provider_strategy": "round-robin",
                "providers": providers,
                "candidate_target": candidate_count,
                "prompt": prompt_rel,
                "request": request_rel,
                "output_dir": rel(execution_dir / "candidates"),
            }
        )
    return {
        "schema_version": SCHEMA_PATCH_SWARM_PROREQ,
        "run_id": run_dir.name,
        "written_at": now_iso(),
        "status": "planned",
        "objective": objective,
        "execution_count": len(executions),
        "candidate_target": candidate_target,
        "max_parallel_agents": max_parallel_agents,
        "providers": providers,
        "live_dispatch_enabled": bool(live),
        "runtime_adapters": {provider: PATCH_SWARM_PROVIDER_RUNTIMES[provider] for provider in providers if provider in PATCH_SWARM_PROVIDER_RUNTIMES},
        "executions": executions,
        "integration_execution": {
            **PATCH_SWARM_INTEGRATOR,
            "status": "queued",
            "depends_on": [execution["id"] for execution in executions],
            "artifact": rel(run_dir / "integration_execution" / "integration_execution.json"),
        },
    }


def patch_swarm_write_report(run_dir: Path, manifest: dict[str, Any], receipt: dict[str, Any] | None = None, integration: dict[str, Any] | None = None, validation: dict[str, Any] | None = None) -> None:
    proreq = read_json(run_dir / "proreq_execution_manifest.json")
    executions = proreq.get("executions") if isinstance(proreq.get("executions"), list) else []
    lines = [
        "# Patch Swarm Decision Report",
        "",
        f"- Run: `{run_dir.name}`",
        f"- Status: `{(validation or {}).get('status') or (integration or {}).get('status') or (receipt or {}).get('status') or manifest.get('status')}`",
        f"- Candidate target: `{manifest.get('candidate_target')}`",
        f"- ProReq executions: `{len(executions)}`",
        f"- Dedicated integrator: `{PATCH_SWARM_INTEGRATOR['id']}`",
        f"- Providers: `{', '.join(manifest.get('providers') or [])}`",
        f"- Autopilot ready: `{manifest.get('autopilot', {}).get('mode')}`",
        "",
        "## Execution Split",
        "",
    ]
    for item in executions:
        lines.append(f"- `{item.get('id')}` candidates={item.get('candidate_target')} status=`{item.get('status')}`")
    if receipt:
        lines.extend(
            [
                "",
                "## Candidate Summary",
                "",
                f"- Candidates generated: `{receipt.get('candidate_count', 0)}`",
                f"- Passed validation: `{receipt.get('passed_count', 0)}`",
                f"- Rejected: `{receipt.get('rejected_count', 0)}`",
                f"- Estimated cost: `${float(receipt.get('estimated_cost_usd') or 0.0):.6f}`",
            ]
        )
    if integration:
        lines.extend(
            [
                "",
                "## Integration",
                "",
                f"- Selected winners: `{integration.get('selected_count', 0)}`",
                f"- Apply: `{integration.get('apply')}`",
                f"- Handoff: `{integration.get('safe_integrator_handoff', '-')}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            f"- Manifest: `{rel(run_dir / 'patch_swarm_manifest.json')}`",
            f"- ProReq execution manifest: `{rel(run_dir / 'proreq_execution_manifest.json')}`",
            f"- Candidate index: `{rel(run_dir / 'candidate_index.json')}`",
            f"- Ranking: `{rel(run_dir / 'ranking.json')}`",
            f"- UI state: `{rel(run_dir / 'ui_state.json')}`",
            f"- Events: `{rel(run_dir / 'events.ndjson')}`",
        ]
    )
    (run_dir / "decision_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def patch_swarm_write_ui_state(run_dir: Path) -> dict[str, Any]:
    manifest = read_json(run_dir / "patch_swarm_manifest.json")
    proreq = read_json(run_dir / "proreq_execution_manifest.json")
    receipt = read_json(run_dir / "patch_swarm_receipt.json")
    integration = read_json(run_dir / "integration_execution" / "integration_execution.json")
    validation = read_json(run_dir / "validation_summary.json")
    ranking = read_json(run_dir / "ranking.json")
    product_metadata = read_json(run_dir / "product_metadata.json")
    approval = read_json(run_dir / "supervised_approval.json")
    decisions = read_json(run_dir / "candidate_decisions.json")
    candidate_count = int(receipt.get("candidate_count") or manifest.get("candidate_target") or 0)
    selected_count = int(integration.get("selected_count") or 0)
    provider_counts = receipt.get("provider_counts") if isinstance(receipt.get("provider_counts"), dict) else {}
    executions = proreq.get("executions") if isinstance(proreq.get("executions"), list) else []
    state = {
        "schema_version": "cento.patch_swarm.ui_state.v1",
        "run_id": run_dir.name,
        "written_at": now_iso(),
        "status": validation.get("status") or integration.get("status") or receipt.get("status") or manifest.get("status", "unknown"),
        "run_dir": rel(run_dir),
        "summary": {
            "candidate_target": manifest.get("candidate_target", 0),
            "candidate_count": candidate_count,
            "proreq_execution_count": len(executions),
            "selected_count": selected_count,
            "estimated_cost_usd": receipt.get("estimated_cost_usd", 0.0),
            "providers": manifest.get("providers", []),
            "provider_counts": provider_counts,
            "max_parallel_agents": manifest.get("max_parallel_agents", 0),
        },
        "lanes": [
            {
                "id": str(item.get("id") or ""),
                "title": str(item.get("title") or ""),
                "status": str(item.get("status") or "planned"),
                "candidate_target": int(item.get("candidate_target") or 0),
                "candidate_count": int(item.get("candidate_count") or 0),
                "winner": str(item.get("winner") or ""),
            }
            for item in executions
        ],
        "ranking": ranking.get("top_candidates", []) if isinstance(ranking.get("top_candidates"), list) else [],
        "artifacts": {
            "manifest": rel(run_dir / "patch_swarm_manifest.json"),
            "candidate_index": rel(run_dir / "candidate_index.json"),
            "ranking": rel(run_dir / "ranking.json"),
            "integration_execution": rel(run_dir / "integration_execution" / "integration_execution.json") if integration else "",
            "validation_summary": rel(run_dir / "validation_summary.json") if validation else "",
            "decision_report": rel(run_dir / "decision_report.md"),
        },
        "product": product_metadata if product_metadata else {},
        "approval": approval if approval else {},
        "candidate_decisions": decisions if decisions else {},
    }
    write_json(run_dir / "ui_state.json", state)
    latest_root = PIPELINE_ROOT / "execution" / "patch-swarm"
    latest_root.mkdir(parents=True, exist_ok=True)
    write_json(latest_root / f"{run_dir.name}_ui_state.json", state)
    write_json(latest_root / "latest_ui_state.json", state)
    return state


def build_patch_swarm_plan(
    run_dir: Path,
    *,
    objective: str = PATCH_SWARM_OBJECTIVE,
    candidate_target: int = 100,
    max_parallel_agents: int = 5,
    providers: list[str] | None = None,
    live: bool = False,
) -> dict[str, Any]:
    run_dir.mkdir(parents=True, exist_ok=True)
    providers = patch_swarm_provider_list(providers)
    candidate_target = max(1, int(candidate_target))
    max_parallel_agents = max(1, int(max_parallel_agents))
    proreq = patch_swarm_execution_manifest(
        run_dir,
        objective=objective or PATCH_SWARM_OBJECTIVE,
        candidate_target=candidate_target,
        max_parallel_agents=max_parallel_agents,
        providers=providers,
        live=live,
    )
    for execution in proreq["executions"]:
        execution_dir = run_dir / "proreq_executions" / str(execution["id"])
        execution_dir.mkdir(parents=True, exist_ok=True)
        request = {
            "schema_version": "cento.patch_swarm.proreq_execution_request.v1",
            "run_id": run_dir.name,
            "execution_id": execution["id"],
            "title": execution["title"],
            "objective": objective or PATCH_SWARM_OBJECTIVE,
            "focus": execution["focus"],
            "candidate_target": execution["candidate_target"],
            "providers": providers,
            "runtime_adapters": {provider: PATCH_SWARM_PROVIDER_RUNTIMES[provider] for provider in providers if provider in PATCH_SWARM_PROVIDER_RUNTIMES},
            "owned_paths": execution["owned_paths"],
            "output_schema": SCHEMA_PATCH_SWARM_CANDIDATE,
            "mutation_policy": "proposal-only; no direct operator worktree mutation",
        }
        write_json(execution_dir / "proreq_request.json", request)
        (execution_dir / "prompt.md").write_text(
            patch_swarm_prompt_text(objective or PATCH_SWARM_OBJECTIVE, execution, providers, int(execution["candidate_target"])),
            encoding="utf-8",
        )
    cost_policy = patch_swarm_cost_policy(candidate_target, max_parallel_agents, providers, live)
    manifest = {
        "schema_version": SCHEMA_PATCH_SWARM,
        "run_id": run_dir.name,
        "created_at": now_iso(),
        "status": "planned",
        "mode": "live" if live else "fixture",
        "objective": objective or PATCH_SWARM_OBJECTIVE,
        "candidate_target": candidate_target,
        "min_candidate_target": 1,
        "max_parallel_agents": max_parallel_agents,
        "providers": providers,
        "live_dispatch_enabled": bool(live),
        "proreq_execution_count": len(proreq["executions"]),
        "integration_execution": PATCH_SWARM_INTEGRATOR,
        "autopilot": {
            "mode": "dry-run-compatible",
            "entrypoint": f"cento parallel-delivery patch-swarm e2e --run-id {run_dir.name} --candidate-target {candidate_target} --max-parallel-agents {max_parallel_agents} --fixture --json",
            "walk_autopilot_status": f"cento walk-autopilot patch-swarm status --run-id {run_dir.name} --json",
        },
        "artifacts": {
            "proreq_execution_manifest": rel(run_dir / "proreq_execution_manifest.json"),
            "candidate_index": rel(run_dir / "candidate_index.json"),
            "ranking": rel(run_dir / "ranking.json"),
            "cost_policy": rel(run_dir / "cost_policy.json"),
            "receipt": rel(run_dir / "patch_swarm_receipt.json"),
            "ui_state": rel(run_dir / "ui_state.json"),
            "validation": rel(run_dir / "validation_summary.json"),
            "decision_report": rel(run_dir / "decision_report.md"),
        },
    }
    write_json(run_dir / "patch_swarm_manifest.json", manifest)
    write_json(run_dir / "proreq_execution_manifest.json", proreq)
    write_json(run_dir / "cost_policy.json", cost_policy)
    write_json(
        run_dir / "autopilot_handoff.json",
        {
            "schema_version": "cento.patch_swarm.autopilot_handoff.v1",
            "run_id": run_dir.name,
            "written_at": now_iso(),
            "status": "planned",
            "commands": [
                f"cento parallel-delivery patch-swarm execute {run_dir.name} --fixture --json",
                f"cento parallel-delivery patch-swarm integrate {run_dir.name} --dry-run --json",
                f"cento parallel-delivery patch-swarm validate {run_dir.name} --json",
            ],
            "budget_policy": rel(run_dir / "cost_policy.json"),
            "ui_state": rel(run_dir / "ui_state.json"),
        },
    )
    write_json(run_dir / "candidate_index.json", {"schema_version": "cento.patch_swarm.candidate_index.v1", "run_id": run_dir.name, "candidates": []})
    write_json(run_dir / "ranking.json", {"schema_version": "cento.patch_swarm.ranking.v1", "run_id": run_dir.name, "top_candidates": []})
    patch_swarm_write_report(run_dir, manifest)
    patch_swarm_write_ui_state(run_dir)
    patch_swarm_event(run_dir, "patch_swarm_planned", {"candidate_target": candidate_target, "providers": providers})
    return manifest


def retarget_patch_swarm_to_sandbox(run_dir: Path, sandbox_root: Path) -> None:
    manifest = read_json(run_dir / "patch_swarm_manifest.json")
    proreq = read_json(run_dir / "proreq_execution_manifest.json")
    executions = [item for item in proreq.get("executions", []) if isinstance(item, dict)]
    providers = patch_swarm_provider_list(manifest.get("providers") if isinstance(manifest.get("providers"), list) else "")
    objective = str(manifest.get("objective") or PATCH_SWARM_OBJECTIVE)
    for execution in executions:
        execution_id = str(execution.get("id") or "execution")
        safe_path = rel(sandbox_root / f"{execution_id}.md")
        execution["owned_paths"] = [safe_path]
        execution_dir = run_dir / "proreq_executions" / execution_id
        request_path = execution_dir / "proreq_request.json"
        request = read_json(request_path)
        if request:
            request["owned_paths"] = [safe_path]
            request["sandboxed_by"] = "self-improve-e2e"
            write_json(request_path, request)
        (execution_dir / "prompt.md").write_text(
            patch_swarm_prompt_text(objective, execution, providers, int(execution.get("candidate_target") or 1)),
            encoding="utf-8",
        )
    proreq["executions"] = executions
    proreq["sandbox_root"] = rel(sandbox_root)
    write_json(run_dir / "proreq_execution_manifest.json", proreq)


def patch_swarm_candidate_patch_text(path: str, candidate_id: str, execution_id: str, provider: str, *, repo_root: Path | None = None) -> str:
    base = repo_root or ROOT
    resolved = Path(path) if Path(path).is_absolute() else base / path
    note = f"Patch Swarm fixture candidate {candidate_id} from {provider} for {execution_id}."
    suffix = Path(path).suffix.lower()
    if suffix == ".json":
        addition = ""
    elif suffix == ".md":
        addition = f"<!-- {note} -->"
    elif suffix in {".js", ".jsx", ".ts", ".tsx"}:
        addition = f"// {note}"
    else:
        addition = f"# {note}"
    if resolved.exists():
        lines = resolved.read_text(encoding="utf-8", errors="ignore").splitlines()
        context = lines[: max(1, min(3, len(lines)))]
        if not context:
            return "\n".join(
                [
                    f"diff --git a/{path} b/{path}",
                    f"--- a/{path}",
                    f"+++ b/{path}",
                    "@@ -0,0 +1 @@",
                    f"+{addition}",
                    "",
                ]
            )
        old_count = len(context)
        new_count = old_count + 1
        hunk_lines = [f"@@ -1,{old_count} +1,{new_count} @@"]
        insert_after_first = suffix == ".json" or context[0].startswith("#!")
        for index, line in enumerate(context):
            hunk_lines.append(f" {line}")
            if insert_after_first and index == 0:
                hunk_lines.append(f"+{addition}")
        if not insert_after_first:
            hunk_lines.insert(1, f"+{addition}")
        return "\n".join(
            [
                f"diff --git a/{path} b/{path}",
                f"--- a/{path}",
                f"+++ b/{path}",
                *hunk_lines,
                "",
            ]
        )
    return "\n".join(
        [
            f"diff --git a/{path} b/{path}",
            "new file mode 100644",
            "index 0000000..e69de29",
            "--- /dev/null",
            f"+++ b/{path}",
            "@@ -0,0 +1 @@",
            f"+{addition}",
            "",
        ]
    )


def patch_swarm_diff_from_content(path: str, content: str) -> str:
    repo_path = path.strip().lstrip("/")
    resolved = resolve_cento_path(repo_path)
    old_lines = resolved.read_text(encoding="utf-8", errors="ignore").splitlines() if resolved.exists() else []
    new_lines = str(content).splitlines()
    from_file = f"a/{repo_path}" if resolved.exists() else "/dev/null"
    to_file = f"b/{repo_path}"
    diff_lines = list(difflib.unified_diff(old_lines, new_lines, fromfile=from_file, tofile=to_file, lineterm=""))
    header = [f"diff --git a/{repo_path} b/{repo_path}"]
    if not resolved.exists():
        header.extend(["new file mode 100644", "index 0000000..e69de29"])
    if len(diff_lines) <= 2:
        return ""
    return "\n".join([*header, *diff_lines]) + "\n"


def patch_swarm_api_task_request(run_dir: Path, execution: dict[str, Any], candidate_id: str, objective: str) -> dict[str, Any]:
    safe_path = f"workspace/runs/parallel-delivery/patch-swarm/{run_dir.name}/api-sandbox/{candidate_id}.md"
    return {
        "schema_version": "cento.patch_swarm.api_patch_request.v1",
        "worker_id": f"api-openai-{candidate_id}",
        "task_id": candidate_id,
        "execution_id": str(execution.get("id") or ""),
        "title": str(execution.get("title") or ""),
        "objective": objective,
        "focus": str(execution.get("focus") or ""),
        "owned_paths": [safe_path],
        "write_paths": [safe_path],
        "output_schema": "patch_proposal.v1",
        "instructions": [
            "Return one small patch_proposal.v1 artifact.",
            f"Use exactly this repo-relative path in owned_path_contents: {safe_path}",
            "The content should be a short markdown note suitable for a sandbox receipt.",
            "Do not request shell commands and do not include secrets.",
        ],
        "validation": ["git apply --check on the generated unified diff"],
    }


def patch_swarm_api_artifact_to_candidate(
    run_dir: Path,
    execution: dict[str, Any],
    candidate_id: str,
    local_index: int,
    artifact_dir: Path,
    worker_result: dict[str, Any],
    proc: subprocess.CompletedProcess[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    execution_id = str(execution.get("id") or "")
    candidate_dir = artifact_dir.parent
    validation_dir = artifact_dir.parent.parent / "validation"
    validation_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = resolve_cento_path(str(worker_result.get("artifact") or rel(artifact_dir / "artifact.json")))
    artifact = read_json(artifact_path)
    cost_receipt_path = resolve_cento_path(str(worker_result.get("cost_receipt") or rel(artifact_dir / "cost_receipt.json")))
    cost_receipt = read_json(cost_receipt_path)
    content = artifact.get("content") if isinstance(artifact.get("content"), dict) else {}
    path_contents = content.get("owned_path_contents") if isinstance(content.get("owned_path_contents"), list) else []
    diffs: list[str] = []
    touched_paths: list[str] = []
    errors: list[str] = []
    for item in path_contents:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "").strip().lstrip("/")
        proposed = str(item.get("content") or "")
        if not path:
            errors.append("artifact owned_path_contents item missing path")
            continue
        diff_text = patch_swarm_diff_from_content(path, proposed)
        if not diff_text:
            errors.append(f"artifact proposed no diff for {path}")
            continue
        touched_paths.append(path)
        diffs.append(diff_text.rstrip())
    if not diffs:
        fallback_path = f"workspace/runs/parallel-delivery/patch-swarm/{run_dir.name}/api-sandbox/{candidate_id}-fallback.md"
        fallback_content = "\n".join(
            [
                f"# API Patch Proposal Fallback {candidate_id}",
                "",
                str(content.get("summary") or "API worker did not return materializable path contents."),
                "",
            ]
        )
        diffs.append(patch_swarm_diff_from_content(fallback_path, fallback_content).rstrip())
        touched_paths.append(fallback_path)
    patch_text = "\n".join(diff for diff in diffs if diff.strip()) + "\n"
    patch_path = candidate_dir / f"{candidate_id}.diff"
    patch_path.write_text(patch_text, encoding="utf-8")
    patch_hash = hashlib.sha256(patch_text.encode("utf-8")).hexdigest()
    apply_check = subprocess.run(["git", "apply", "--check", str(patch_path)], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    patch_apply_ok = apply_check.returncode == 0
    artifact_completed = artifact.get("status") == "completed" and content.get("schema_version") == "patch_proposal.v1"
    if proc.returncode != 0:
        errors.append((proc.stderr or proc.stdout)[-1000:] or "api worker command failed")
    if not artifact_completed:
        errors.extend(str(item) for item in artifact.get("errors") or ["api worker artifact was not completed"])
    if not patch_apply_ok:
        errors.append("git apply check failed")
    passed = artifact_completed and patch_apply_ok and not errors
    cost = float(worker_result.get("cost_usd_estimate") or cost_receipt.get("cost_usd_estimate") or 0.0)
    validation_path = validation_dir / f"{candidate_id}.json"
    validation = {
        "schema_version": "cento.patch_swarm.candidate_validation.v1",
        "run_id": run_dir.name,
        "candidate_id": candidate_id,
        "execution_id": execution_id,
        "status": "passed" if passed else "rejected",
        "checks": [
            {"name": "api_worker_exit", "status": "passed" if proc.returncode == 0 else "failed", "stderr_tail": proc.stderr[-1000:]},
            {"name": "api_worker_artifact", "status": "passed" if artifact_completed else "failed", "artifact": rel(artifact_path)},
            {"name": "patch_shape", "status": "passed" if patch_text.startswith("diff --git ") else "failed"},
            {"name": "git_apply_check", "status": "passed" if patch_apply_ok else "failed", "stderr_tail": apply_check.stderr[-1000:]},
        ],
        "api_worker": {
            "artifact": rel(artifact_path),
            "cost_receipt": rel(cost_receipt_path),
            "worker_receipt": str(worker_result.get("worker_receipt") or ""),
        },
        "written_at": now_iso(),
    }
    write_json(validation_path, validation)
    candidate = {
        "schema_version": SCHEMA_PATCH_SWARM_CANDIDATE,
        "id": candidate_id,
        "run_id": run_dir.name,
        "execution_id": execution_id,
        "task_id": execution_id,
        "provider": "api-openai",
        "provider_runtime": PATCH_SWARM_PROVIDER_RUNTIMES["api-openai"],
        "candidate_index": local_index,
        "status": "validated" if passed else "rejected",
        "owned_paths": [str(path) for path in execution.get("owned_paths", []) if isinstance(path, str)],
        "touched_paths": touched_paths,
        "patch": {
            "format": "unified_diff",
            "patch_file": rel(patch_path),
            "sha256": patch_hash,
        },
        "cluster_key": hashlib.sha256(f"{execution_id}:{','.join(touched_paths)}:api".encode("utf-8")).hexdigest()[:16],
        "score": round(98.5 - cost * 100, 3) if passed else round(40.0 - cost * 100, 3),
        "cost_usd_estimate": round(cost, 6),
        "duration_ms_estimate": 0.0,
        "validation_receipt": rel(validation_path),
        "api_worker_artifact": rel(artifact_path),
        "api_worker_cost_receipt": rel(cost_receipt_path),
        "api_worker_returncode": proc.returncode,
        "errors": errors,
        "written_at": now_iso(),
    }
    candidate_path = candidate_dir / f"{candidate_id}.json"
    write_json(candidate_path, candidate)
    candidate["candidate_receipt"] = rel(candidate_path)
    return candidate, validation


def run_patch_swarm_api_candidate(
    run_dir: Path,
    execution: dict[str, Any],
    candidate_id: str,
    local_index: int,
    *,
    objective: str,
    api_profile: str,
    api_config: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    candidate_dir = run_dir / "proreq_executions" / str(execution.get("id") or "") / "candidates"
    artifact_dir = candidate_dir / f"{candidate_id}-api-worker"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    request_path = artifact_dir / "task_request.json"
    write_json(request_path, patch_swarm_api_task_request(run_dir, execution, candidate_id, objective))
    command = [
        sys.executable,
        str(ROOT / "scripts" / "cento_openai_worker.py"),
        "run",
        rel(request_path),
        "--out-dir",
        rel(artifact_dir),
        "--profile",
        api_profile,
        "--config",
        api_config,
        "--output-schema",
        "patch_proposal.v1",
        "--reserved-cost-usd",
        str(PATCH_SWARM_API_COST_ESTIMATE_USD),
        "--json",
    ]
    proc = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=180)
    try:
        worker_result = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        worker_result = {"status": "failed", "errors": ["api worker stdout was not JSON"], "stdout_tail": proc.stdout[-1000:]}
    return patch_swarm_api_artifact_to_candidate(run_dir, execution, candidate_id, local_index, artifact_dir, worker_result, proc)


def execute_patch_swarm(
    run_dir: Path,
    *,
    fixture: bool = True,
    budget_cap_usd: float | None = None,
    max_budget_usd: float | None = None,
    api_sandbox_candidates: int = 1,
    api_profile: str = PATCH_SWARM_API_PROFILE,
    api_config: str = str(ROOT / ".cento" / "api_workers.yaml"),
) -> dict[str, Any]:
    manifest = read_json(run_dir / "patch_swarm_manifest.json")
    proreq = read_json(run_dir / "proreq_execution_manifest.json")
    executions = [item for item in proreq.get("executions", []) if isinstance(item, dict)]
    if not manifest or not executions:
        receipt = {"schema_version": SCHEMA_PATCH_SWARM_RECEIPT, "run_id": run_dir.name, "status": "blocked", "errors": ["patch swarm plan is missing"]}
        write_json(run_dir / "patch_swarm_receipt.json", receipt)
        return receipt
    if not fixture:
        gate = patch_swarm_budget_gate(
            run_dir,
            budget_cap_usd=budget_cap_usd,
            max_budget_usd=max_budget_usd,
            api_sandbox_candidates=api_sandbox_candidates,
        )
        if not bool(manifest.get("live_dispatch_enabled")):
            receipt = {"schema_version": SCHEMA_PATCH_SWARM_RECEIPT, "run_id": run_dir.name, "status": "blocked", "errors": ["live dispatch requires a live-enabled plan"], "budget_gate": rel(run_dir / "usage_guard.json")}
            write_json(run_dir / "patch_swarm_receipt.json", receipt)
            return receipt
        if gate.get("status") != "passed":
            receipt = {"schema_version": SCHEMA_PATCH_SWARM_RECEIPT, "run_id": run_dir.name, "status": "blocked", "errors": gate.get("blockers", []), "budget_gate": rel(run_dir / "usage_guard.json")}
            write_json(run_dir / "patch_swarm_receipt.json", receipt)
            patch_swarm_event(run_dir, "patch_swarm_live_blocked", {"blockers": gate.get("blockers", [])})
            return receipt
    elif not (run_dir / "usage_guard.json").exists():
        write_json(
            run_dir / "usage_guard.json",
            {
                "schema_version": "cento.patch_swarm.live_budget_gate.v1",
                "run_id": run_dir.name,
                "status": "not_required_fixture",
                "estimated_cost_usd": 0.0,
                "written_at": now_iso(),
            },
        )
    providers = patch_swarm_provider_list(manifest.get("providers") if isinstance(manifest.get("providers"), list) else "")
    repo_root = patch_swarm_selected_repo_root(run_dir)
    candidate_rows: list[dict[str, Any]] = []
    validation_rows: list[dict[str, Any]] = []
    global_index = 0
    api_dispatch_count = 0
    api_dispatch_limit = max(0, int(api_sandbox_candidates or 0))
    for execution in executions:
        execution_id = str(execution.get("id") or "")
        execution_dir = run_dir / "proreq_executions" / execution_id
        candidate_dir = execution_dir / "candidates"
        validation_dir = execution_dir / "validation"
        candidate_dir.mkdir(parents=True, exist_ok=True)
        validation_dir.mkdir(parents=True, exist_ok=True)
        owned_paths = [str(path) for path in execution.get("owned_paths", []) if isinstance(path, str)]
        touched_path = owned_paths[0] if owned_paths else f"workspace/runs/parallel-delivery/patch-swarm/{run_dir.name}/{execution_id}.md"
        local_candidates = []
        for local_index in range(1, int(execution.get("candidate_target") or 0) + 1):
            global_index += 1
            provider = providers[(global_index - 1) % len(providers)]
            candidate_id = f"{execution_id}-cand-{local_index:03d}"
            if not fixture and provider == "api-openai" and api_dispatch_count < api_dispatch_limit:
                api_dispatch_count += 1
                candidate, validation = run_patch_swarm_api_candidate(
                    run_dir,
                    execution,
                    candidate_id,
                    local_index,
                    objective=str(manifest.get("objective") or PATCH_SWARM_OBJECTIVE),
                    api_profile=api_profile,
                    api_config=api_config,
                )
                append_patch_swarm_usage(run_dir, candidate)
                local_candidates.append(candidate)
                candidate_rows.append(candidate)
                validation_rows.append(validation)
                continue
            patch_text = patch_swarm_candidate_patch_text(touched_path, candidate_id, execution_id, provider, repo_root=repo_root)
            patch_hash = hashlib.sha256(patch_text.encode("utf-8")).hexdigest()
            cluster_key = hashlib.sha256(f"{execution_id}:{touched_path}:{local_index % 4}".encode("utf-8")).hexdigest()[:16]
            quality_passed = local_index % 11 != 0
            duplicate_penalty = (local_index % 4) * 0.75
            cost = 0.0
            patch_path = candidate_dir / f"{candidate_id}.diff"
            patch_path.write_text(patch_text, encoding="utf-8")
            apply_check = subprocess.run(["git", "apply", "--check", str(patch_path)], cwd=repo_root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            patch_apply_ok = apply_check.returncode == 0
            passed = quality_passed and patch_apply_ok
            score = round(100.0 - duplicate_penalty - (0 if passed else 50) - cost * 100, 3)
            validation_path = validation_dir / f"{candidate_id}.json"
            validation = {
                "schema_version": "cento.patch_swarm.candidate_validation.v1",
                "run_id": run_dir.name,
                "candidate_id": candidate_id,
                "execution_id": execution_id,
                "status": "passed" if passed else "rejected",
                "checks": [
                    {"name": "schema", "status": "passed"},
                    {"name": "owned_path", "status": "passed"},
                    {"name": "patch_shape", "status": "passed" if patch_text.startswith("diff --git ") else "failed"},
                    {"name": "git_apply_check", "status": "passed" if patch_apply_ok else "failed", "stderr_tail": apply_check.stderr[-1000:]},
                    {"name": "fixture_rejection_gate", "status": "passed" if passed else "failed"},
                ],
                "written_at": now_iso(),
            }
            write_json(validation_path, validation)
            candidate = {
                "schema_version": SCHEMA_PATCH_SWARM_CANDIDATE,
                "id": candidate_id,
                "run_id": run_dir.name,
                "execution_id": execution_id,
                "task_id": execution_id,
                "provider": provider,
                "provider_runtime": PATCH_SWARM_PROVIDER_RUNTIMES.get(provider, {}),
                "candidate_index": local_index,
                "status": "validated" if passed else "rejected",
                "owned_paths": owned_paths,
                "touched_paths": [touched_path],
                "patch": {
                    "format": "unified_diff",
                    "patch_file": rel(patch_path),
                    "sha256": patch_hash,
                },
                "cluster_key": cluster_key,
                "score": score,
                "cost_usd_estimate": cost,
                "duration_ms_estimate": 350 + (local_index % 7) * 40,
                "validation_receipt": rel(validation_path),
                "errors": [] if passed else (["git apply check failed"] if not patch_apply_ok else ["fixture rejection gate marked this candidate as lower quality"]),
                "written_at": now_iso(),
            }
            candidate_path = candidate_dir / f"{candidate_id}.json"
            write_json(candidate_path, candidate)
            candidate["candidate_receipt"] = rel(candidate_path)
            append_patch_swarm_usage(run_dir, candidate)
            local_candidates.append(candidate)
            candidate_rows.append(candidate)
            validation_rows.append(validation)
        execution["status"] = "completed"
        execution["candidate_count"] = len(local_candidates)
        execution["candidate_receipts"] = [item["candidate_receipt"] for item in local_candidates]

    cluster_counter = Counter(str(item.get("cluster_key") or "") for item in candidate_rows)
    clusters = [
        {
            "cluster_key": cluster_key,
            "candidate_count": count,
            "execution_ids": sorted({str(item.get("execution_id") or "") for item in candidate_rows if item.get("cluster_key") == cluster_key}),
            "providers": sorted({str(item.get("provider") or "") for item in candidate_rows if item.get("cluster_key") == cluster_key}),
        }
        for cluster_key, count in sorted(cluster_counter.items())
    ]
    passed_candidates = [item for item in candidate_rows if item.get("status") == "validated"]
    ranked = sorted(passed_candidates, key=lambda item: (-float(item.get("score") or 0), float(item.get("cost_usd_estimate") or 0), str(item.get("id") or "")))
    provider_counts = Counter(str(item.get("provider") or "unknown") for item in candidate_rows)
    receipt = {
        "schema_version": SCHEMA_PATCH_SWARM_RECEIPT,
        "run_id": run_dir.name,
        "written_at": now_iso(),
        "status": "candidates_generated",
        "mode": manifest.get("mode", "fixture"),
        "candidate_count": len(candidate_rows),
        "passed_count": len(passed_candidates),
        "rejected_count": len(candidate_rows) - len(passed_candidates),
        "proreq_execution_count": len(executions),
        "provider_counts": dict(sorted(provider_counts.items())),
        "estimated_cost_usd": round(sum(float(item.get("cost_usd_estimate") or 0.0) for item in candidate_rows), 6),
        "api_sandbox_candidates_requested": api_dispatch_limit if not fixture else 0,
        "api_sandbox_candidates_dispatched": api_dispatch_count,
        "candidate_index": rel(run_dir / "candidate_index.json"),
        "ranking": rel(run_dir / "ranking.json"),
        "dedupe_clusters": rel(run_dir / "dedupe_clusters.json"),
        "cost_ledger": rel(run_dir / "cost_ledger.json"),
    }
    candidate_index = {
        "schema_version": "cento.patch_swarm.candidate_index.v1",
        "run_id": run_dir.name,
        "written_at": now_iso(),
        "candidate_count": len(candidate_rows),
        "candidates": candidate_rows,
    }
    ranking = {
        "schema_version": "cento.patch_swarm.ranking.v1",
        "run_id": run_dir.name,
        "written_at": now_iso(),
        "ranking_policy": "validation-first, lower-cost tie break, deterministic id tie break",
        "top_candidates": ranked[: max(20, len(executions))],
    }
    cost_ledger = {
        "schema_version": "cento.patch_swarm.cost_ledger.v1",
        "run_id": run_dir.name,
        "written_at": now_iso(),
        "total_estimated_cost_usd": receipt["estimated_cost_usd"],
        "provider_counts": receipt["provider_counts"],
        "provider_costs_usd": {
            provider: round(sum(float(item.get("cost_usd_estimate") or 0.0) for item in candidate_rows if item.get("provider") == provider), 6)
            for provider in sorted(provider_counts)
        },
    }
    proreq["status"] = "completed"
    proreq["written_at"] = now_iso()
    write_json(run_dir / "proreq_execution_manifest.json", proreq)
    write_json(run_dir / "candidate_index.json", candidate_index)
    write_json(run_dir / "ranking.json", ranking)
    write_json(run_dir / "dedupe_clusters.json", {"schema_version": "cento.patch_swarm.dedupe_clusters.v1", "run_id": run_dir.name, "clusters": clusters})
    write_json(run_dir / "cost_ledger.json", cost_ledger)
    write_json(run_dir / "patch_swarm_receipt.json", receipt)
    manifest["status"] = "candidates_generated"
    manifest["updated_at"] = now_iso()
    write_json(run_dir / "patch_swarm_manifest.json", manifest)
    patch_swarm_write_report(run_dir, manifest, receipt)
    patch_swarm_write_ui_state(run_dir)
    patch_swarm_event(run_dir, "patch_swarm_candidates_generated", {"candidate_count": len(candidate_rows), "estimated_cost_usd": receipt["estimated_cost_usd"]})
    return receipt


def patch_swarm_factory_run_dir(run_dir: Path, value: str = "") -> Path:
    if value:
        path = Path(value)
        return path if path.is_absolute() else ROOT / path
    return FACTORY_RUNS_ROOT / f"patch-swarm-{run_dir.name}"


def patch_swarm_factory_plan_payload(run_dir: Path, factory_run_dir: Path, selected: list[dict[str, Any]]) -> dict[str, Any]:
    tasks: list[dict[str, Any]] = []
    for candidate in selected:
        task_id = str(candidate.get("execution_id") or candidate.get("task_id") or candidate.get("id"))
        touched_paths = text_list(candidate.get("touched_paths"))
        tasks.append(
            {
                "id": task_id,
                "title": f"Promote Patch Swarm winner: {candidate.get('id')}",
                "lane": "builder",
                "node": "linux",
                "owned_scope": touched_paths,
                "goal": f"Apply selected Patch Swarm candidate `{candidate.get('id')}` through Factory Safe Integrator.",
                "expected_outputs": [{"path": path, "description": "Selected Patch Swarm candidate output"} for path in touched_paths],
                "validation_commands": [f"python3 -m json.tool {shlex.quote(str(factory_run_dir / 'patches' / task_id / 'validation-result.json'))}"],
                "no_model_eligible": True,
                "risk": "low",
                "dependencies": [],
            }
        )
    return {
        "schema_version": "factory-plan/v1",
        "run_id": factory_run_dir.name,
        "request": {
            "raw": f"Promote Patch Swarm run {run_dir.name} into Factory Safe Integrator.",
            "normalized_goal": "Convert selected candidate_patch.v1 receipts into Factory patch bundles and release evidence.",
        },
        "package": "patch-swarm-promotion",
        "mode": "dispatch_dry_run",
        "risk": "medium",
        "budget": {
            "ai_call_budget": 0,
            "estimated_cost_usd": round(sum(float(item.get("cost_usd_estimate") or 0.0) for item in selected), 6),
            "strong_model_calls_allowed": 0,
            "cheap_worker_calls_allowed": 0,
        },
        "shared_paths": [],
        "tasks": tasks,
        "integration": {
            "strategy": "safe_integrator_from_patch_swarm",
            "merge_order": [str(item.get("execution_id") or item.get("task_id") or item.get("id")) for item in selected],
            "required_docs": [],
        },
        "validation": {
            "minimum_tier": "tier0",
            "requires_screenshots": False,
            "requires_api_smoke": False,
            "requires_human_review": True,
        },
        "evidence": {
            "run_dir": rel(factory_run_dir),
            "summary": rel(factory_run_dir / "summary.md"),
        },
        "created_at": now_iso(),
        "source_patch_swarm": {
            "run_id": run_dir.name,
            "run_dir": rel(run_dir),
            "candidate_index": rel(run_dir / "candidate_index.json"),
            "safe_integrator_handoff": rel(run_dir / "safe_integrator_handoff.json"),
        },
    }


def copy_patch_swarm_outputs_to_factory(factory_run_dir: Path, selected: list[dict[str, Any]], source_run_dir: Path) -> dict[str, Any]:
    patches: list[dict[str, Any]] = []
    for candidate in selected:
        task_id = str(candidate.get("execution_id") or candidate.get("task_id") or candidate.get("id"))
        patch_dir = factory_run_dir / "patches" / task_id
        task_dir = factory_run_dir / "tasks" / task_id
        patch_dir.mkdir(parents=True, exist_ok=True)
        task_dir.mkdir(parents=True, exist_ok=True)
        patch_value = str((candidate.get("patch") or {}).get("patch_file") or "")
        patch_src = resolve_cento_path(patch_value)
        if patch_src.exists():
            shutil.copy2(patch_src, patch_dir / "patch.diff")
        else:
            (patch_dir / "patch.diff").write_text("", encoding="utf-8")
        touched_paths = text_list(candidate.get("touched_paths"))
        (patch_dir / "changed-files.txt").write_text("\n".join(touched_paths) + ("\n" if touched_paths else ""), encoding="utf-8")
        (patch_dir / "diffstat.txt").write_text("\n".join(f" {path} | Patch Swarm selected candidate" for path in touched_paths) + ("\n" if touched_paths else ""), encoding="utf-8")
        validation_src = resolve_cento_path(str(candidate.get("validation_receipt") or ""))
        validation_payload = read_json(validation_src) if validation_src.exists() else {}
        validation_status = "passed" if str(candidate.get("status") or "") == "validated" and not patch_swarm_candidate_errors(candidate, source_run_dir) else "failed"
        write_json(
            patch_dir / "validation-result.json",
            {
                "schema_version": "factory-validation-result/v1",
                "status": validation_status,
                "source_validation_receipt": rel(validation_src) if validation_src.exists() else "",
                "candidate_receipt": str(candidate.get("candidate_receipt") or ""),
                "ai_calls_used": 0,
                "estimated_ai_cost_usd": 0,
                "generated_at": now_iso(),
            },
        )
        (patch_dir / "handoff.md").write_text(
            "\n".join(
                [
                    f"# Patch Swarm Candidate {candidate.get('id')}",
                    "",
                    f"- Source run: `{source_run_dir.name}`",
                    f"- Provider: `{candidate.get('provider')}`",
                    f"- Score: `{candidate.get('score')}`",
                    f"- Candidate receipt: `{candidate.get('candidate_receipt') or ''}`",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        evidence_dir = patch_dir / "evidence"
        evidence_dir.mkdir(exist_ok=True)
        write_json(evidence_dir / "candidate-receipt.json", candidate)
        patch = {
            "schema_version": "factory-patch/v1",
            "run_id": factory_run_dir.name,
            "task_id": task_id,
            "issue_id": None,
            "base_sha": factory_dispatch.git_sha(),
            "worker_run_id": str(candidate.get("id") or ""),
            "patch_file": "patch.diff",
            "changed_files": touched_paths,
            "diffstat_file": "diffstat.txt",
            "handoff_file": "handoff.md",
            "validation_result": "validation-result.json",
            "evidence_paths": ["evidence/candidate-receipt.json"],
            "collection_state": "collected" if patch_src.exists() else "missing",
            "owned_path_check": "passed",
            "git_apply_check": "pending",
            "docs_registry_gate": "pending",
            "integration_status": "candidate",
        }
        write_json(patch_dir / "patch.json", patch)
        patches.append({"task_id": task_id, "patch_bundle": rel(patch_dir / "patch.json"), "state": patch["collection_state"], "integration_status": "candidate"})
        write_json(task_dir / "patch-swarm-candidate.json", candidate)
    summary = {
        "schema_version": "factory-patch-collection/v1",
        "run_id": factory_run_dir.name,
        "patches": patches,
        "ai_calls_used": 0,
        "estimated_ai_cost_usd": 0,
        "generated_at": now_iso(),
    }
    write_json(factory_run_dir / "patch-collection-summary.json", summary)
    return summary


def promote_patch_swarm_to_factory(
    run_dir: Path,
    selected: list[dict[str, Any]],
    *,
    factory_run: str = "",
    apply: bool = False,
    validate_each: bool = False,
    branch: str = "",
    worktree: str = "",
    limit: int = 0,
) -> dict[str, Any]:
    factory_run_dir = patch_swarm_factory_run_dir(run_dir, factory_run)
    factory_run_dir.mkdir(parents=True, exist_ok=True)
    write_json(factory_run_dir / "factory-plan.json", patch_swarm_factory_plan_payload(run_dir, factory_run_dir, selected))
    (factory_run_dir / "summary.md").write_text(f"# Patch Swarm Promotion\n\nSource Patch Swarm: `{run_dir.name}`\n", encoding="utf-8")
    factory_tool.materialize_run(factory_run_dir)
    factory_dispatch.generate_queue(factory_run_dir)
    patch_collection = copy_patch_swarm_outputs_to_factory(factory_run_dir, selected, run_dir)
    apply_plan = factory_integrator.create_apply_plan(factory_run_dir)
    fanout = factory_integrator.validate_fanout(factory_run_dir)
    factory_integrator.update_integration_state(factory_run_dir)
    result: dict[str, Any] = {
        "schema_version": "cento.patch_swarm.factory_promotion.v1",
        "run_id": run_dir.name,
        "factory_run_dir": rel(factory_run_dir),
        "factory_plan": rel(factory_run_dir / "factory-plan.json"),
        "patch_collection": rel(factory_run_dir / "patch-collection-summary.json"),
        "apply_plan": rel(factory_run_dir / "integration" / "apply-plan.json"),
        "validation_fanout": rel(factory_run_dir / "integration" / "validation-fanout.json"),
        "candidate_count": len(apply_plan.get("candidates") or []),
        "rejected_count": len(apply_plan.get("rejected") or []),
        "fanout_status": fanout.get("status"),
        "apply": bool(apply),
        "status": "ready_for_apply" if not apply and apply_plan.get("candidates") and fanout.get("status") == "passed" else ("validation_fanout_failed" if fanout.get("status") != "passed" else "planned"),
        "patch_collection_count": len(patch_collection.get("patches") or []),
        "written_at": now_iso(),
    }
    if apply:
        factory_integrator.prepare_branch(factory_run_dir, branch=branch, worktree=worktree or None)
        apply_result = factory_integrator.apply_patches(factory_run_dir, worktree=worktree or None, branch=branch, limit=limit, validate_each=validate_each)
        integrated_validation = factory_integrator.validate_integrated(factory_run_dir)
        release = factory_integrator.render_release_candidate(factory_run_dir)
        result.update(
            {
                "status": "release_candidate_ready" if integrated_validation.get("decision") == "approve" else "apply_blocked",
                "apply_result": rel(factory_run_dir / "integration" / "applied-patches.json"),
                "applied_count": len(apply_result.get("applied") or []),
                "apply_rejected_count": len(apply_result.get("rejected") or []),
                "integrated_validation": rel(factory_run_dir / "integration" / "integrated-validation.json"),
                "release_candidate": release.get("release_candidate", ""),
            }
        )
    write_json(run_dir / "factory_promotion.json", result)
    return result


def integrate_patch_swarm(
    run_dir: Path,
    *,
    apply: bool = False,
    factory_run: str = "",
    validate_each: bool = False,
    branch: str = "",
    worktree: str = "",
    limit: int = 0,
) -> dict[str, Any]:
    manifest = read_json(run_dir / "patch_swarm_manifest.json")
    proreq = read_json(run_dir / "proreq_execution_manifest.json")
    candidate_index = read_json(run_dir / "candidate_index.json")
    candidates = [item for item in candidate_index.get("candidates", []) if isinstance(item, dict)]
    executions = [item for item in proreq.get("executions", []) if isinstance(item, dict)]
    selected: list[dict[str, Any]] = []
    blockers: list[str] = []
    for execution in executions:
        execution_id = str(execution.get("id") or "")
        lane_candidates = [
            item
            for item in candidates
            if str(item.get("execution_id") or "") == execution_id and str(item.get("status") or "") == "validated" and not patch_swarm_candidate_errors(item, run_dir)
        ]
        lane_candidates.sort(key=lambda item: (-float(item.get("score") or 0), float(item.get("cost_usd_estimate") or 0), str(item.get("id") or "")))
        if lane_candidates:
            winner = lane_candidates[0]
            selected.append(winner)
            execution["winner"] = winner.get("id")
            execution["status"] = "winner_selected"
        else:
            blockers.append(f"no validated candidate for {execution_id}")
            execution["status"] = "blocked"
    integration_dir = run_dir / "integration_execution"
    integration_dir.mkdir(parents=True, exist_ok=True)
    receipts: list[str] = []
    for index, candidate in enumerate(selected, start=1):
        receipt_path = integration_dir / f"{candidate['execution_id']}_integration_receipt.json"
        payload = {
            "schema_version": "cento.patch_swarm.integration_receipt.v1",
            "run_id": run_dir.name,
            "sequence": index,
            "execution_id": candidate["execution_id"],
            "candidate_id": candidate["id"],
            "status": "accepted_for_safe_integrator",
            "apply": False,
            "patch_file": candidate.get("patch", {}).get("patch_file", ""),
            "touched_paths": candidate.get("touched_paths", []),
            "provider": candidate.get("provider", ""),
            "score": candidate.get("score"),
            "written_at": now_iso(),
        }
        write_json(receipt_path, payload)
        receipts.append(rel(receipt_path))
    handoff_path = run_dir / "safe_integrator_handoff.json"
    handoff = {
        "schema_version": "cento.patch_swarm.safe_integrator_handoff.v1",
        "run_id": run_dir.name,
        "written_at": now_iso(),
        "status": "ready" if selected and not blockers else "blocked",
        "apply": bool(apply),
        "factory_safe_integrator_required": True,
        "selected_candidates": [
            {
                "candidate_id": item.get("id"),
                "execution_id": item.get("execution_id"),
                "provider": item.get("provider"),
                "patch_file": item.get("patch", {}).get("patch_file", ""),
                "touched_paths": item.get("touched_paths", []),
                "score": item.get("score"),
            }
            for item in selected
        ],
        "integration_receipts": receipts,
        "next_gate": "Factory/Safe Integrator apply plan; optional apply stays in isolated integration worktree",
        "blockers": blockers,
    }
    factory_promotion: dict[str, Any] = {}
    if selected and not blockers and (apply or factory_run):
        factory_promotion = promote_patch_swarm_to_factory(
            run_dir,
            selected,
            factory_run=factory_run,
            apply=apply,
            validate_each=validate_each,
            branch=branch,
            worktree=worktree,
            limit=limit,
        )
        handoff["factory_promotion"] = rel(run_dir / "factory_promotion.json")
        handoff["factory_run_dir"] = factory_promotion.get("factory_run_dir", "")
        handoff["status"] = "applied" if factory_promotion.get("status") == "release_candidate_ready" else handoff["status"]
    write_json(handoff_path, handoff)
    integration_status = "completed" if selected and not blockers else "blocked"
    if factory_promotion and apply and factory_promotion.get("status") != "release_candidate_ready":
        integration_status = "blocked"
        blockers.append(str(factory_promotion.get("status") or "factory_promotion_blocked"))
    integration = {
        "schema_version": SCHEMA_PATCH_SWARM_INTEGRATION,
        "run_id": run_dir.name,
        "written_at": now_iso(),
        "id": PATCH_SWARM_INTEGRATOR["id"],
        "title": PATCH_SWARM_INTEGRATOR["title"],
        "status": integration_status,
        "apply": bool(apply),
        "apply_requested": bool(apply),
        "selected_count": len(selected),
        "expected_selected_count": len(executions),
        "selected_candidates": [item.get("id") for item in selected],
        "integration_receipts": receipts,
        "safe_integrator_handoff": rel(handoff_path),
        "factory_promotion": rel(run_dir / "factory_promotion.json") if factory_promotion else "",
        "factory_run_dir": factory_promotion.get("factory_run_dir", "") if factory_promotion else "",
        "factory_promotion_status": factory_promotion.get("status", "") if factory_promotion else "",
        "blockers": blockers,
    }
    write_json(integration_dir / "integration_execution.json", integration)
    proreq["status"] = "integrated" if not blockers else "blocked"
    proreq["written_at"] = now_iso()
    write_json(run_dir / "proreq_execution_manifest.json", proreq)
    manifest["status"] = "integrated" if not blockers else "blocked"
    manifest["updated_at"] = now_iso()
    write_json(run_dir / "patch_swarm_manifest.json", manifest)
    patch_swarm_write_report(run_dir, manifest, read_json(run_dir / "patch_swarm_receipt.json"), integration)
    patch_swarm_write_ui_state(run_dir)
    patch_swarm_event(run_dir, "patch_swarm_integrated", {"status": integration["status"], "selected_count": len(selected)})
    return integration


def validate_patch_swarm_run(run_dir: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, detail: str = "") -> None:
        checks.append({"name": name, "status": "passed" if passed else "failed", "detail": detail})

    manifest = read_json(run_dir / "patch_swarm_manifest.json")
    proreq = read_json(run_dir / "proreq_execution_manifest.json")
    receipt = read_json(run_dir / "patch_swarm_receipt.json")
    candidate_index = read_json(run_dir / "candidate_index.json")
    integration = read_json(run_dir / "integration_execution" / "integration_execution.json")
    ui_state = read_json(run_dir / "ui_state.json")
    executions = proreq.get("executions") if isinstance(proreq.get("executions"), list) else []
    candidates = candidate_index.get("candidates") if isinstance(candidate_index.get("candidates"), list) else []
    providers = set(manifest.get("providers") if isinstance(manifest.get("providers"), list) else [])
    add("manifest.schema", manifest.get("schema_version") == SCHEMA_PATCH_SWARM)
    add("proreq.schema", proreq.get("schema_version") == SCHEMA_PATCH_SWARM_PROREQ)
    add("proreq.execution_count", len(executions) >= 10, f"{len(executions)} execution(s)")
    add("candidate_index.schema", candidate_index.get("schema_version") == "cento.patch_swarm.candidate_index.v1")
    add("candidate_count.target", len(candidates) >= int(manifest.get("candidate_target") or 0), f"{len(candidates)} candidate(s)")
    invalid_candidates = [str(item.get("id") or "") for item in candidates if patch_swarm_candidate_errors(item, run_dir)]
    add("candidate_receipts.schema", not invalid_candidates, ", ".join(invalid_candidates[:10]))
    add("providers.codex", "codex-exec" in providers)
    add("providers.claude", "claude-code" in providers)
    add("providers.openai", "api-openai" in providers)
    add("receipt.schema", receipt.get("schema_version") == SCHEMA_PATCH_SWARM_RECEIPT)
    add("receipt.counts_match", int(receipt.get("candidate_count") or 0) == len(candidates))
    add("integration.schema", integration.get("schema_version") == SCHEMA_PATCH_SWARM_INTEGRATION)
    add("integration.dedicated", integration.get("id") == PATCH_SWARM_INTEGRATOR["id"])
    add("integration.selected_per_execution", int(integration.get("selected_count") or 0) == len(executions), f"{integration.get('selected_count')} selected")
    add("safe_integrator_handoff.exists", (run_dir / "safe_integrator_handoff.json").exists())
    if integration.get("factory_promotion"):
        promotion = read_json(run_dir / "factory_promotion.json")
        add("factory_promotion.schema", promotion.get("schema_version") == "cento.patch_swarm.factory_promotion.v1")
        add("factory_promotion.fanout", promotion.get("fanout_status") in {"passed", "blocked"}, str(promotion.get("fanout_status") or ""))
    add("ui_state.schema", ui_state.get("schema_version") == "cento.patch_swarm.ui_state.v1")
    add("decision_report.exists", (run_dir / "decision_report.md").exists())
    status = "passed" if all(item["status"] == "passed" for item in checks) else "failed"
    validation = {
        "schema_version": SCHEMA_PATCH_SWARM_VALIDATION,
        "run_id": run_dir.name,
        "written_at": now_iso(),
        "status": status,
        "checks": checks,
    }
    write_json(run_dir / "validation_summary.json", validation)
    manifest["status"] = "validated" if status == "passed" else "validation_failed"
    manifest["updated_at"] = now_iso()
    write_json(run_dir / "patch_swarm_manifest.json", manifest)
    patch_swarm_write_report(run_dir, manifest, receipt, integration, validation)
    patch_swarm_write_ui_state(run_dir)
    patch_swarm_event(run_dir, "patch_swarm_validated", {"status": status})
    return validation


def plan_manifest(run_dir: Path) -> dict[str, Any]:
    passes = []
    for index, item in enumerate(WORKSTREAMS, start=1):
        passes.append(
            {
                "id": item["id"],
                "title": item["title"],
                "sequence": index,
                "operator_prompt": pass_prompt(item),
                "image_task": image_task(item),
                "expected_outputs": [
                    "pro_backend_request.json",
                    "image_generation_request.json",
                    "story_index.json",
                    "parallel_patch_workset.json",
                    "manifest_integration_policy.json",
                    "integration_plan.json",
                    "validation_plan.json",
                    "hard_proreq_evidence.json",
                ],
            }
        )
    return {
        "schema_version": SCHEMA_PLAN,
        "id": run_dir.name,
        "created_at": now_iso(),
        "goal": BASE_VISION,
        "target": {
            "workers": 10,
            "integrator_validator_lanes": "2-3",
            "latency_target": "2-3 minutes",
            "marginal_cost_target_usd": "3-5",
            "ai_fallback_policy": "only-if-needed after deterministic gates cannot classify",
        },
        "hard_proreq_passes": passes,
        "integration": {
            "lanes": ["patch-safety", "focused-validation", "release-evidence"],
            "mutation_policy": "workers never mutate repo files directly; local integrator/materializer owns mutation",
            "release_policy": "produce release packet and receipts; do not auto-merge main",
        },
        "validation": {
            "required": [
                "each Hard ProReq pass completed",
                "each generated workset passes cento workset check",
                "demo workset has 10 tasks and max_parallel 10",
                "receipt records Pro/image live status and skip/failure reasons",
            ]
        },
        "demo": {
            "workset": rel(run_dir / "demo" / "workset.json"),
            "runtime": "fixture",
            "max_parallel": 10,
            "validation": "smoke",
        },
    }


def write_plan(run_dir: Path) -> dict[str, Any]:
    manifest = plan_manifest(run_dir)
    write_json(run_dir / "implementation_manifest.json", manifest)
    return manifest


def execute_proreq_pass(pass_spec: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    env_updates = {
        "CENTO_HARD_PROREQ_IMAGE_TASK": str(pass_spec["image_task"]),
        "CENTO_HARD_PROREQ_STEP_TIMEOUT": str(args.step_timeout),
        "CENTO_HARD_PROREQ_PRO_TIMEOUT": str(args.pro_timeout),
        "CENTO_HARD_PROREQ_IMAGE_TIMEOUT": str(args.image_timeout),
    }
    if args.live_pro and os.environ.get("OPENAI_API_KEY"):
        env_updates["CENTO_HARD_PROREQ_DISPATCH_PRO"] = "1"
    if args.reference_screenshot:
        env_updates["CENTO_HARD_PROREQ_REFERENCE_SCREENSHOT"] = args.reference_screenshot
    with scoped_env(env_updates):
        response = app.dev_pipeline_start_pipeline_run(
            pipeline_payload(str(pass_spec["operator_prompt"]), args.reference_screenshot),
            spawn=False,
        )
        run_id = str(response.get("run_id") or "")
        app.dev_pipeline_spawn_execution_e2e(app.DEV_PIPELINE_STUDIO_ROOT, app.HARD_PROREQ_PROJECT_ID, app.HARD_PROREQ_TEMPLATE_ID, run_id)
        final_payload = wait_for_pipeline(run_id, args.per_run_timeout, args.poll_seconds)
    artifacts = summarize_hard_proreq(run_id)
    return {
        "id": pass_spec["id"],
        "title": pass_spec["title"],
        "sequence": pass_spec["sequence"],
        "run_id": run_id,
        "status": str(final_payload.get("status") or ""),
        "duration_seconds": int(final_payload.get("duration_seconds") or 0),
        "started_at": str(final_payload.get("started_at") or ""),
        "finished_at": str(final_payload.get("finished_at") or ""),
        "artifacts": artifacts,
        "workset_check": run_workset_check(str(artifacts.get("parallel_patch_workset") or "")),
    }


def write_demo_workset(run_dir: Path) -> Path:
    tasks = []
    for index, path in enumerate(DEMO_TARGET_PATHS, start=1):
        tasks.append(
            {
                "id": f"demo-lane-{index:02d}",
                "worker_id": f"fixture-worker-{index:02d}",
                "task": f"Patch demo lane {index:02d}",
                "description": "Fixture worker proves the parallel delivery worker contract through dry-run integration.",
                "write_paths": [path],
                "read_paths": ["docs/parallel-ai-delivery-roadmap.md"],
                "depends_on": [],
                "cost_usd_estimate": 0.0,
            }
        )
    workset = {
        "schema_version": "cento.workset.v1",
        "id": f"parallel_delivery_demo_{run_dir.name.lower()}",
        "mode": "fast",
        "max_parallel": 10,
        "execution_model": "parallel",
        "integration": "sequential",
        "routes": ["/parallel-delivery/demo"],
        "read_paths": ["docs/parallel-ai-delivery-roadmap.md"],
        "tasks": tasks,
    }
    path = run_dir / "demo" / "workset.json"
    write_json(path, workset)
    return path


def run_demo(run_dir: Path, *, execute: bool = True) -> dict[str, Any]:
    workset_path = write_demo_workset(run_dir)
    check = run_workset_check(rel(workset_path))
    receipt: dict[str, Any] = {
        "schema_version": "cento.parallel_delivery.demo_receipt.v1",
        "written_at": now_iso(),
        "status": "planned",
        "workset": rel(workset_path),
        "workset_check": check,
    }
    if execute and check.get("status") == "passed":
        command = [
            "python3",
            "scripts/cento_workset.py",
            "execute",
            rel(workset_path),
            "--max-parallel",
            "10",
            "--runtime",
            "fixture",
            "--integrate",
            "sequential",
            "--validation",
            "smoke",
            "--allow-dirty-owned",
            "--json",
        ]
        result = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        payload: dict[str, Any] = {}
        try:
            payload = json.loads(result.stdout or "{}")
        except json.JSONDecodeError:
            payload = {}
        workset_receipt = payload.get("workset_receipt")
        receipt.update(
            {
                "status": "completed" if result.returncode == 0 and payload.get("status") == "completed" else "failed",
                "command": command,
                "exit_code": result.returncode,
                "stdout": result.stdout[-4000:],
                "stderr": result.stderr[-4000:],
                "workset_receipt": workset_receipt,
                "workset_result": payload,
            }
        )
    write_json(run_dir / "demo" / "demo_receipt.json", receipt)
    return receipt


def compose_execution_manifest(run_dir: Path, receipt: dict[str, Any], demo_receipt: dict[str, Any] | None) -> dict[str, Any]:
    passes = receipt.get("passes") if isinstance(receipt.get("passes"), list) else []
    manifest = {
        "schema_version": "cento.parallel_delivery.execution_manifest.v1",
        "run_id": run_dir.name,
        "written_at": now_iso(),
        "source_plan": rel(run_dir / "implementation_manifest.json"),
        "proreq_receipt": rel(run_dir / "proreq_receipt.json"),
        "demo_receipt": rel(run_dir / "demo" / "demo_receipt.json") if demo_receipt else "",
        "workstreams": [
            {
                "id": item.get("id"),
                "title": item.get("title"),
                "hard_proreq_run_id": item.get("run_id"),
                "story_count": item.get("artifacts", {}).get("story_count") if isinstance(item.get("artifacts"), dict) else 0,
                "parallel_patch_workset": item.get("artifacts", {}).get("parallel_patch_workset") if isinstance(item.get("artifacts"), dict) else "",
                "workset_check": item.get("workset_check", {}).get("status") if isinstance(item.get("workset_check"), dict) else "",
            }
            for item in passes
        ],
        "integrator_validator_lanes": ["patch-safety", "focused-validation", "release-evidence"],
        "fallback_policy": {
            "mode": "only-if-needed",
            "trigger": "deterministic gates cannot classify conflict, missing evidence, failed validation, or ambiguity",
            "reviewer_profile": "api-mini-integrator",
        },
        "demo": {
            "status": (demo_receipt or {}).get("status", ""),
            "workset": (demo_receipt or {}).get("workset", ""),
            "workset_receipt": (demo_receipt or {}).get("workset_receipt", ""),
        },
    }
    write_json(run_dir / "execution_manifest.json", manifest)
    return manifest


def validate_run(run_dir: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(name: str, status: str, detail: str = "") -> None:
        checks.append({"name": name, "status": status, "detail": detail})

    plan = read_json(run_dir / "implementation_manifest.json")
    receipt = read_json(run_dir / "proreq_receipt.json")
    execution = read_json(run_dir / "execution_manifest.json")
    demo = read_json(run_dir / "demo" / "demo_receipt.json")
    add("plan.schema", "passed" if plan.get("schema_version") == SCHEMA_PLAN else "failed")
    add("receipt.schema", "passed" if receipt.get("schema_version") == SCHEMA_RECEIPT else "failed")
    add("execution.schema", "passed" if execution.get("schema_version") == "cento.parallel_delivery.execution_manifest.v1" else "failed")
    passes = receipt.get("passes") if isinstance(receipt.get("passes"), list) else []
    expected_pass_count = int(receipt.get("expected_pass_count") or len(WORKSTREAMS))
    add("proreq.pass_count", "passed" if len(passes) == expected_pass_count else "failed", f"{len(passes)}/{expected_pass_count}")
    completed = [item for item in passes if item.get("status") == "completed"]
    add("proreq.completed", "passed" if len(completed) == len(passes) and passes else "failed", f"{len(completed)}/{len(passes)}")
    workset_passed = 0
    for item in passes:
        if isinstance(item.get("workset_check"), dict) and item["workset_check"].get("status") == "passed":
            workset_passed += 1
    add("proreq.workset_checks", "passed" if workset_passed == len(passes) and passes else "failed", f"{workset_passed}/{len(passes)}")
    demo_required = bool(receipt.get("demo_required", True))
    if demo_required:
        add("demo.receipt", "passed" if demo.get("schema_version") == "cento.parallel_delivery.demo_receipt.v1" else "failed")
        if demo:
            add("demo.status", "passed" if demo.get("status") in {"completed", "planned"} else "failed", str(demo.get("status") or ""))
    else:
        add("demo.skipped", "passed")
    status = "passed" if all(check["status"] == "passed" for check in checks) else "failed"
    payload = {"schema_version": SCHEMA_VALIDATION, "written_at": now_iso(), "status": status, "checks": checks}
    write_json(run_dir / "validation_summary.json", payload)
    return payload


def validate_selected_run(run_dir: Path) -> dict[str, Any]:
    fixture_run_dir = selected_patch_swarm_fixture_e2e_run_dir(run_dir)
    if fixture_run_dir:
        validation = validation_e2e_tool.validate_e2e_run(fixture_run_dir)
        status = "passed" if validation.get("ok") else "failed"
        return {
            "schema_version": SCHEMA_VALIDATION,
            "written_at": now_iso(),
            "status": status,
            "run_kind": "patch_swarm_fixture_e2e",
            "validated_run_dir": rel(fixture_run_dir),
            "checks": [
                {
                    "name": "patch_swarm_fixture_e2e",
                    "status": status,
                    "detail": "; ".join(str(item) for item in validation.get("errors") or []),
                }
            ],
            "patch_swarm_e2e": validation,
        }
    payload = validate_run(run_dir)
    payload.setdefault("run_kind", "parallel_delivery")
    return payload


def status_for_selected_run(run_dir: Path) -> dict[str, Any]:
    if (run_dir / "worker-status.json").exists():
        payload = worker_status_tool.status_for_run(run_dir)
        payload.update(
            {
                "schema_version": "cento.parallel_delivery.status.v1",
                "run_kind": "patch_swarm_worker_status",
                "status": "dry_run_dispatch_planned" if payload.get("ok") else "blocked",
                "validation": "worker_status_ready" if payload.get("ok") else "worker_status_failed",
                "demo": "not_applicable",
                "execution_manifest": "",
            }
        )
        return payload
    fixture_run_dir = selected_patch_swarm_fixture_e2e_run_dir(run_dir)
    if fixture_run_dir:
        summary = read_json(fixture_run_dir / "validation-summary.json")
        return {
            "schema_version": "cento.parallel_delivery.status.v1",
            "run_kind": "patch_swarm_fixture_e2e",
            "run_dir": rel(run_dir),
            "validated_run_dir": rel(fixture_run_dir),
            "status": summary.get("state") or summary.get("overall", "unknown"),
            "pass_count": int(summary.get("candidate_count") or 0),
            "validation": summary.get("overall", "unknown"),
            "demo": "not_applicable",
            "execution_manifest": "",
        }
    receipt = read_json(run_dir / "proreq_receipt.json")
    validation = read_json(run_dir / "validation_summary.json")
    demo = read_json(run_dir / "demo" / "demo_receipt.json")
    return {
        "schema_version": "cento.parallel_delivery.status.v1",
        "run_kind": "parallel_delivery",
        "run_dir": rel(run_dir),
        "status": receipt.get("status", "unknown"),
        "pass_count": len(receipt.get("passes") or []),
        "validation": validation.get("status", "unknown"),
        "demo": demo.get("status", "unknown"),
        "execution_manifest": rel(run_dir / "execution_manifest.json"),
    }


def self_latest_dir() -> Path:
    return SELF_IMPROVE_RUNS_ROOT / "latest"


def self_improve_latest_run_dir() -> Path | None:
    if not SELF_IMPROVE_RUNS_ROOT.exists():
        return None
    candidates = [
        path
        for path in SELF_IMPROVE_RUNS_ROOT.iterdir()
        if path.is_dir() and path.name != "latest" and (path / "nightly_cycle_manifest.json").exists()
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def resolve_self_run_dir(value: str | None, *, create: bool = False) -> Path:
    if value:
        path = Path(value)
        if not path.is_absolute():
            path = ROOT / path
    else:
        path = SELF_IMPROVE_RUNS_ROOT / now_stamp() if create else self_improve_latest_run_dir()
        if path is None:
            path = SELF_IMPROVE_RUNS_ROOT / now_stamp()
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def write_self_json(run_dir: Path, name: str, payload: Any, *, mirror_latest: bool = True) -> str:
    path = run_dir / name
    write_json(path, payload)
    if mirror_latest:
        write_json(self_latest_dir() / name, payload)
    return rel(path)


def previous_continuous_handoff() -> tuple[dict[str, Any], str]:
    if not CONTINUOUS_PROREQ_ROOT.exists():
        return {}, ""
    candidates = sorted(CONTINUOUS_PROREQ_ROOT.glob("*/validation_handoff.json"), key=lambda path: path.stat().st_mtime)
    if not candidates:
        return {}, ""
    path = candidates[-1]
    return read_json(path), rel(path)


def resolve_self_seed() -> dict[str, Any]:
    latest_next = self_latest_dir() / "next_cycle_request.json"
    latest_payload = read_json(latest_next)
    if latest_payload:
        return {
            "source": "latest_next_cycle_request",
            "path": rel(latest_next),
            "request": latest_payload,
            "source_payload": latest_payload,
        }
    handoff, handoff_path = previous_continuous_handoff()
    if handoff:
        request = handoff.get("next_cycle_request") if isinstance(handoff.get("next_cycle_request"), dict) else {}
        return {
            "source": "previous_continuous_proreq_handoff",
            "path": handoff_path,
            "request": request or handoff,
            "source_payload": handoff,
        }
    request = {
        "objective": "Run a four-pass Cento nightly self-improvement planning cycle.",
        "required_first_wave": [
            "Plan scope and guardrails.",
            "Plan architecture.",
            "Plan integration and workset strategy.",
            "Plan validation, promotion, and the next-night request.",
        ],
        "budget_model_policy": AGENT_PREFERRED_COMPUTE_POLICY,
    }
    return {"source": "default_seed", "path": "", "request": request, "source_payload": request}


def seed_objective(seed: dict[str, Any]) -> str:
    request = seed.get("request") if isinstance(seed.get("request"), dict) else {}
    objective = str(request.get("objective") or "").strip()
    if objective:
        return objective
    return "Run a four-pass Cento nightly self-improvement planning cycle."


def path_from_repo_value(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    return path


def workset_declared_path_policy(workset_path: str) -> dict[str, Any]:
    workset = read_json(path_from_repo_value(workset_path)) if workset_path else {}
    tasks = workset.get("tasks") if isinstance(workset.get("tasks"), list) else []
    api_worker_declared = any(
        isinstance(task, dict)
        and (
            str(task.get("api_profile") or "")
            or str(task.get("output_schema") or "")
            or str(task.get("worker_id") or "").startswith("api-")
        )
        for task in tasks
    )
    return {
        "runtime": "api-openai" if api_worker_declared else "",
        "allow_creates": api_worker_declared,
        "reason": "api-worker-created file plans may own new paths" if api_worker_declared else "default existing-file edit policy",
    }


def workset_task_count(workset_path: str) -> int:
    workset = read_json(path_from_repo_value(workset_path)) if workset_path else {}
    tasks = workset.get("tasks") if isinstance(workset.get("tasks"), list) else []
    return len([item for item in tasks if isinstance(item, dict)])


def pro_state_for_run(root: Path) -> dict[str, Any]:
    plan = read_json(root / "pro_backend_plan.json")
    response = read_json(root / "pro_backend_response.json")
    response_body = response.get("response") if isinstance(response.get("response"), dict) else {}
    response_status = str(response.get("status") or response_body.get("status") or "")
    plan_valid = plan.get("schema_version") == "cento.hard_proreq_backend_plan.v1" and bool(str(plan.get("summary") or "").strip())
    reason = ""
    if not plan_valid:
        reason = "Pro plan artifacts were missing or blank when summarized."
    elif response_status == "failed":
        reason = str(response.get("error") or "")
    elif response_status == "skipped":
        reason = str(response.get("skip_code") or "")
    return {
        "status": "completed" if plan_valid else "degraded",
        "response_status": response_status,
        "dispatch_status": str(response.get("dispatch_status") or response_body.get("status") or ""),
        "skip_code": str(response.get("skip_code") or ""),
        "model": str(response.get("model") or response_body.get("model") or ""),
        "plan_present": bool(plan),
        "plan_valid": plan_valid,
        "reason": reason,
        "plan": rel(root / "pro_backend_plan.json"),
        "response": rel(root / "pro_backend_response.json"),
    }


def image_state_for_run(root: Path) -> dict[str, Any]:
    response = read_json(root / "image_generation_response.json")
    response_body = response.get("response") if isinstance(response.get("response"), dict) else {}
    error_payload = response_body.get("error") if isinstance(response_body.get("error"), dict) else {}
    status = str(response.get("status") or "")
    http_status = response.get("http_status")
    return {
        "requested": bool(response),
        "status": status or "missing",
        "blocking": False,
        "model": str(response.get("model") or "gpt-image-2"),
        "http_status": http_status,
        "reason": str(error_payload.get("message") or response.get("error") or response.get("skip_code") or ""),
        "generated_screenshot": bool(response.get("output_image")),
        "evidence": rel(root / "image_generation_response.json"),
    }


def pass_next_guidance(pass_index: int, title: str, record: dict[str, Any], seed: dict[str, Any]) -> str:
    if record.get("status") == "degraded":
        return (
            f"Use pass {pass_index} only as failure evidence in the next pass. "
            f"Repair blockers: {', '.join(record.get('blocking_reasons') or ['unclassified degraded pass'])}."
        )
    if pass_index < len(SELF_IMPROVE_PASS_FOCUS):
        return f"Use pass {pass_index} {title} guidance to drive pass {pass_index + 1}: {SELF_IMPROVE_PASS_FOCUS[pass_index]['title']}."
    return f"Write the next nightly cycle request from pass {pass_index} validation and promotion guidance for: {seed_objective(seed)}"


def self_improve_prompt(pass_index: int, focus: dict[str, str], seed: dict[str, Any], prior_records: list[dict[str, Any]]) -> str:
    request = seed.get("request") if isinstance(seed.get("request"), dict) else {}
    prior = prior_records[-1] if prior_records else {}
    prior_status = str(prior.get("status") or "none")
    prior_guidance = str(prior.get("next_guidance") or "")
    if prior and prior_status == "degraded":
        prior_guidance = "FAILURE EVIDENCE ONLY: " + prior_guidance
    return (
        f"Nightly Cento self-improvement loop pass {pass_index}/4: {focus['title']}.\n\n"
        f"Seed source: {seed.get('source')} {seed.get('path') or ''}\n"
        f"Objective:\n{seed_objective(seed)}\n\n"
        f"Seed request JSON:\n{json.dumps(request, indent=2, sort_keys=False)[:6000]}\n\n"
        f"Focus for this pass:\n{focus['focus']}\n\n"
        f"Previous pass status: {prior_status}\n"
        f"Previous pass guidance and next-step request:\n{prior_guidance or 'No previous pass; establish scope and guardrails first.'}\n\n"
        "Return backend-only planning artifacts for Cento. Include integration manifests, validation manifests, "
        "workset path-policy guidance, nonblocking image evidence handling, promotion criteria, spend controls, "
        "agent-preferred compute routing, residual risks, and an exact next-step request. Do not propose automatic "
        "implementation execution; the loop must plan, gate, recommend, and stop."
    )


def execute_self_improve_pass(pass_index: int, focus: dict[str, str], seed: dict[str, Any], prior_records: list[dict[str, Any]], args: argparse.Namespace) -> dict[str, Any]:
    prompt = self_improve_prompt(pass_index, focus, seed, prior_records)
    env_updates = {
        "CENTO_HARD_PROREQ_IMAGE_TASK": (
            "Create a dense Cento operator UI image prompt for the nightly self-improvement loop. "
            "Show four sequential ProReq passes, nonblocking image evidence, validation gates, "
            "promotion recommendation, and next-cycle request."
        ),
        "CENTO_HARD_PROREQ_STEP_TIMEOUT": str(args.step_timeout),
        "CENTO_HARD_PROREQ_PRO_TIMEOUT": str(args.pro_timeout),
        "CENTO_HARD_PROREQ_IMAGE_TIMEOUT": str(args.image_timeout),
    }
    if args.live_pro and os.environ.get("OPENAI_API_KEY"):
        env_updates["CENTO_HARD_PROREQ_DISPATCH_PRO"] = "1"
    if args.reference_screenshot:
        env_updates["CENTO_HARD_PROREQ_REFERENCE_SCREENSHOT"] = args.reference_screenshot
    with scoped_env(env_updates):
        response = app.dev_pipeline_start_pipeline_run(pipeline_payload(prompt, args.reference_screenshot), spawn=False)
        run_id_value = response.get("run_id")
        if not run_id_value and isinstance(response.get("execution_run"), dict):
            run_id_value = response["execution_run"].get("run_id")
        run_id = str(run_id_value or "")
        if not args.plan_only:
            app.dev_pipeline_spawn_execution_e2e(app.DEV_PIPELINE_STUDIO_ROOT, app.HARD_PROREQ_PROJECT_ID, app.HARD_PROREQ_TEMPLATE_ID, run_id)
            final_payload = wait_for_pipeline(run_id, args.per_run_timeout, args.poll_seconds)
        else:
            final_payload = pipeline_run_payload(run_id)
    root = hard_proreq_root(run_id)
    artifacts = summarize_hard_proreq(run_id)
    pro_state = pro_state_for_run(root)
    image_state = image_state_for_run(root)
    path_policy = workset_declared_path_policy(str(artifacts.get("parallel_patch_workset") or ""))
    workset_check = run_workset_check(
        str(artifacts.get("parallel_patch_workset") or ""),
        runtime=str(path_policy.get("runtime") or ""),
        allow_creates=bool(path_policy.get("allow_creates")),
    )
    workset_tasks = workset_task_count(str(artifacts.get("parallel_patch_workset") or ""))
    blocking_reasons: list[str] = []
    final_status = str(final_payload.get("status") or "")
    if final_status and final_status != "completed":
        blocking_reasons.append(f"child run status is {final_status}")
    if pro_state["status"] != "completed":
        blocking_reasons.append(str(pro_state.get("reason") or "missing or blank Pro artifacts"))
    if workset_check.get("status") != "passed":
        blocking_reasons.append("workset check failed under declared path policy")
    status = "completed" if not blocking_reasons else "degraded"
    record = {
        "schema_version": SCHEMA_SELF_PASS,
        "cycle_pass": pass_index,
        "pass_id": focus["id"],
        "title": focus["title"],
        "status": status,
        "blocking_reasons": blocking_reasons,
        "child_run_id": run_id,
        "child_run_status": final_status,
        "child_run_dir": rel(root),
        "pro_state": pro_state,
        "image_state": image_state,
        "counts": {
            "workstreams": int(artifacts.get("story_count") or 0),
            "stories": int(artifacts.get("story_count") or 0),
            "workset_tasks": workset_tasks,
        },
        "artifacts": artifacts,
        "workset_path_policy": path_policy,
        "workset_check": workset_check,
        "next_guidance": "",
        "prompt_excerpt": prompt[:3000],
        "written_at": now_iso(),
    }
    record["next_guidance"] = pass_next_guidance(pass_index, focus["title"], record, seed)
    return record


def self_improve_validation(run_dir: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(kind: str, name: str, status: str, detail: str = "") -> None:
        checks.append({"kind": kind, "name": name, "status": status, "detail": detail})

    manifest = read_json(run_dir / "nightly_cycle_manifest.json")
    add("blocking", "manifest.schema", "passed" if manifest.get("schema_version") == SCHEMA_SELF_MANIFEST else "failed")
    pass_records = [read_json(run_dir / f"pass_{index:02d}_child_run_summary.json") for index in range(1, 5)]
    add("blocking", "pass.count", "passed" if all(pass_records) else "failed", f"{sum(1 for item in pass_records if item)}/4")
    for index, record in enumerate(pass_records, start=1):
        add("blocking", f"pass_{index:02d}.status", "passed" if record.get("status") == "completed" else "failed", str(record.get("blocking_reasons") or ""))
        pro_state = record.get("pro_state") if isinstance(record.get("pro_state"), dict) else {}
        add("blocking", f"pass_{index:02d}.pro_artifacts", "passed" if pro_state.get("plan_valid") else "failed", str(pro_state.get("reason") or ""))
        workset_check = record.get("workset_check") if isinstance(record.get("workset_check"), dict) else {}
        add("blocking", f"pass_{index:02d}.workset_policy", "passed" if workset_check.get("status") == "passed" else "failed", str(workset_check.get("stderr") or workset_check.get("errors") or ""))
        image_state = record.get("image_state") if isinstance(record.get("image_state"), dict) else {}
        add("nonblocking", f"pass_{index:02d}.image_lane", "passed" if image_state.get("status") in {"completed", "skipped"} else "evidence", str(image_state.get("reason") or image_state.get("status") or ""))
    latest_manifest = read_json(self_latest_dir() / "nightly_cycle_manifest.json")
    latest_cycle_id = str(latest_manifest.get("cycle_id") or "")
    add(
        "blocking",
        "latest.mirror_current",
        "passed" if latest_cycle_id == manifest.get("cycle_id") and bool(manifest.get("cycle_id")) else "failed",
        latest_cycle_id or "missing latest manifest",
    )
    latest_drift_errors: list[str] = []
    for index, record in enumerate(pass_records, start=1):
        latest_record = read_json(self_latest_dir() / f"pass_{index:02d}_child_run_summary.json")
        if latest_record.get("cycle_id") != manifest.get("cycle_id") or latest_record.get("child_run_id") != record.get("child_run_id"):
            latest_drift_errors.append(f"pass_{index:02d}")
    if read_json(self_latest_dir() / "loop_metrics.json").get("cycle_id") != manifest.get("cycle_id"):
        latest_drift_errors.append("loop_metrics")
    if read_json(self_latest_dir() / "promotion_recommendation.json").get("cycle_id") != manifest.get("cycle_id"):
        latest_drift_errors.append("promotion_recommendation")
    if read_json(self_latest_dir() / "evidence_handoff.json").get("cycle_id") != manifest.get("cycle_id"):
        latest_drift_errors.append("evidence_handoff")
    if read_json(self_latest_dir() / "next_cycle_request.json").get("source_cycle") != manifest.get("cycle_id"):
        latest_drift_errors.append("next_cycle_request")
    add(
        "blocking",
        "latest.artifact_drift",
        "passed" if not latest_drift_errors else "failed",
        ", ".join(latest_drift_errors),
    )
    blocking = [item for item in checks if item["kind"] == "blocking"]
    nonblocking = [item for item in checks if item["kind"] == "nonblocking"]
    status = "passed" if all(item["status"] == "passed" for item in blocking) else "failed"
    return {
        "schema_version": SCHEMA_SELF_GATES,
        "cycle_id": manifest.get("cycle_id", run_dir.name),
        "status": status,
        "blocking": blocking,
        "nonblocking": nonblocking,
        "written_at": now_iso(),
    }


def promotion_recommendation(pass_records: list[dict[str, Any]], gates: dict[str, Any]) -> dict[str, Any]:
    if gates.get("status") != "passed":
        blocking_names = [str(item.get("name")) for item in gates.get("blocking", []) if isinstance(item, dict) and item.get("status") != "passed"]
        value = "repair_pipeline_first" if any("pro_artifacts" in name or "workset_policy" in name or "latest" in name for name in blocking_names) else "do_not_promote"
        rationale = "Promotion is blocked by unresolved validation gates: " + ", ".join(blocking_names)
    else:
        pass4 = pass_records[3] if len(pass_records) >= 4 else {}
        policy = pass4.get("workset_path_policy") if isinstance(pass4.get("workset_path_policy"), dict) else {}
        if policy.get("allow_creates"):
            value = "normalize_run_4"
            rationale = "Pass 4 is valid under the explicit API-worker create-file policy; normalize it before any implementation dispatch."
        else:
            value = "promote_run_2"
            rationale = "All gates passed and no create-file normalization is required; pass 2 is the safest directly promotable baseline."
    return {
        "schema_version": SCHEMA_SELF_PROMOTION,
        "cycle_id": gates.get("cycle_id", ""),
        "recommendation": value,
        "allowed_values": ["promote_run_2", "normalize_run_4", "do_not_promote", "repair_pipeline_first"],
        "rationale": rationale,
        "implementation_execution": "blocked until explicit operator follow-up",
        "written_at": now_iso(),
    }


def next_cycle_request_payload(seed: dict[str, Any], pass_records: list[dict[str, Any]], gates: dict[str, Any], recommendation: dict[str, Any]) -> dict[str, Any]:
    repair = gates.get("status") != "passed"
    last_guidance = str((pass_records[-1] if pass_records else {}).get("next_guidance") or "")
    objective = (
        "Repair the Cento nightly self-improvement loop before considering promotion."
        if repair
        else "Continue Cento nightly self-improvement from the validated pass 4 guidance and promotion recommendation."
    )
    return {
        "schema_version": SCHEMA_SELF_NEXT,
        "objective": objective,
        "source_cycle": str(gates.get("cycle_id") or ""),
        "seed_objective": seed_objective(seed),
        "promotion_recommendation": recommendation.get("recommendation"),
        "repair_focused": repair,
        "required_first_wave": [
            "Resolve any failed blocking validation gates before implementation dispatch.",
            "Keep image generation failures as nonblocking evidence unless a backend dependency is explicitly declared.",
            "Use `cento workset check WORKSET --runtime api-openai` only for API-worker-created file plans; plain checks remain strict.",
            "Prefer Codex/Claude agent lanes for 70-80% of eligible follow-up work when weekly utilization is above 30%.",
            "Do not execute implementation worksets automatically from the nightly loop.",
        ],
        "context_artifacts": [rel(path) for path in run_dir_paths_for_cycle(str(gates.get("cycle_id") or ""))],
        "last_pass_guidance": last_guidance,
        "budget_model_policy": AGENT_PREFERRED_COMPUTE_POLICY,
        "written_at": now_iso(),
    }


def run_dir_paths_for_cycle(cycle_id: str) -> list[Path]:
    if not cycle_id:
        return []
    run_dir = SELF_IMPROVE_RUNS_ROOT / cycle_id
    return [
        run_dir / "nightly_cycle_manifest.json",
        run_dir / "validation_gates.json",
        run_dir / "loop_metrics.json",
        run_dir / "promotion_recommendation.json",
        run_dir / "evidence_handoff.json",
    ]


def evidence_handoff_payload(run_dir: Path, pass_records: list[dict[str, Any]], gates: dict[str, Any], recommendation: dict[str, Any]) -> dict[str, Any]:
    artifacts = [
        "nightly_cycle_manifest.json",
        *[f"pass_{index:02d}_child_run_summary.json" for index in range(1, 5)],
        "validation_gates.json",
        "loop_metrics.json",
        "promotion_recommendation.json",
        "next_cycle_request.json",
    ]
    return {
        "schema_version": SCHEMA_SELF_HANDOFF,
        "cycle_id": run_dir.name,
        "status": gates.get("status"),
        "promotion_recommendation": recommendation.get("recommendation"),
        "run_dir": rel(run_dir),
        "latest_dir": rel(self_latest_dir()),
        "artifacts": [{"name": name, "path": rel(run_dir / name), "latest_path": rel(self_latest_dir() / name)} for name in artifacts],
        "child_runs": [
            {
                "pass": record.get("cycle_pass"),
                "run_id": record.get("child_run_id"),
                "run_dir": record.get("child_run_dir"),
                "status": record.get("status"),
                "workset": record.get("artifacts", {}).get("parallel_patch_workset") if isinstance(record.get("artifacts"), dict) else "",
            }
            for record in pass_records
        ],
        "human_summary": (
            "Nightly loop completed validation and stopped before implementation dispatch. "
            f"Promotion recommendation: {recommendation.get('recommendation')}."
        ),
        "written_at": now_iso(),
    }


def loop_metrics_payload(run_dir: Path, started: float, pass_records: list[dict[str, Any]]) -> dict[str, Any]:
    degraded = [record for record in pass_records if record.get("status") != "completed"]
    promotable = [record for record in pass_records if record.get("workset_check", {}).get("status") == "passed"]
    return {
        "schema_version": SCHEMA_SELF_METRICS,
        "cycle_id": run_dir.name,
        "duration_seconds": round(time.perf_counter() - started, 3),
        "spend_estimate": {
            "planning_target_usd": AGENT_PREFERRED_COMPUTE_POLICY["target_spend_usd_max"],
            "planning_hard_cap_usd": AGENT_PREFERRED_COMPUTE_POLICY["hard_spend_usd_max"],
            "implementation_spend_usd": 0.0,
            "note": "No implementation worksets are executed by the nightly loop.",
        },
        "pass_statuses": {str(record.get("pass_id")): record.get("status") for record in pass_records},
        "degraded_pass_count": len(degraded),
        "workset_promotability": {
            "passed_declared_policy_count": len(promotable),
            "total": len(pass_records),
        },
        "compute_routing_policy": AGENT_PREFERRED_COMPUTE_POLICY,
        "written_at": now_iso(),
    }


def self_cron_block(schedule_time: str) -> str:
    hour, minute = parse_cron_time(schedule_time)
    log_path = ROOT / "workspace" / "logs" / "ai-self-improvement-nightly.log"
    command = (
        f"cd {shlex.quote(str(ROOT))} && "
        f"./scripts/cento.sh parallel-delivery self-improve run --json >> {shlex.quote(str(log_path))} 2>&1"
    )
    return "\n".join([SELF_CRON_BEGIN, f"{minute} {hour} * * * {command}", SELF_CRON_END, ""])


def parse_cron_time(value: str) -> tuple[int, int]:
    try:
        hour_text, minute_text = value.split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
    except (ValueError, AttributeError) as exc:
        raise ValueError("--time must be HH:MM") from exc
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError("--time must be HH:MM using a 24-hour clock")
    return hour, minute


def strip_self_cron_block(text: str) -> str:
    if SELF_CRON_BEGIN not in text:
        return text.rstrip() + ("\n" if text.strip() else "")
    before, rest = text.split(SELF_CRON_BEGIN, 1)
    if SELF_CRON_END not in rest:
        return before.rstrip() + "\n"
    _block, after = rest.split(SELF_CRON_END, 1)
    return (before + after).strip() + ("\n" if (before + after).strip() else "")


def read_crontab(crontab_file: str = "") -> str:
    if crontab_file:
        try:
            return Path(crontab_file).read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""
    proc = subprocess.run(["crontab", "-l"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return proc.stdout if proc.returncode == 0 else ""


def write_crontab(text: str, crontab_file: str = "") -> None:
    if crontab_file:
        path = Path(crontab_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return
    proc = subprocess.run(["crontab", "-"], input=text, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "crontab install failed")


def self_e2e_latest_dir() -> Path:
    return SELF_IMPROVE_E2E_RUNS_ROOT / "latest"


def resolve_self_e2e_run_dir(value: str | None, *, create: bool = False) -> Path:
    if value:
        path = Path(value)
        if not path.is_absolute() and ("/" not in value and "\\" not in value):
            path = SELF_IMPROVE_E2E_RUNS_ROOT / value
        elif not path.is_absolute():
            path = ROOT / path
    else:
        path = SELF_IMPROVE_E2E_RUNS_ROOT / f"self-improve-e2e-{now_stamp()}"
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def mirror_self_e2e_latest(run_dir: Path) -> None:
    latest = self_e2e_latest_dir()
    if latest.exists() or latest.is_symlink():
        shutil.rmtree(latest)
    shutil.copytree(run_dir, latest)


def jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return rows
    for line in lines:
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def self_e2e_source_payload(run_dir: Path, *, fixture_only: bool) -> dict[str, Any]:
    latest_next = self_latest_dir() / "next_cycle_request.json"
    latest_payload = read_json(latest_next)
    if latest_payload:
        payload = {
            "schema_version": "cento.ai_self_improvement_e2e.source.v1",
            "status": "ready",
            "source": "latest_next_cycle_request",
            "path": rel(latest_next),
            "request": latest_payload,
            "planning_loop": {"status": "skipped_existing_latest"},
            "written_at": now_iso(),
        }
        write_json(run_dir / "self_improve_source.json", payload)
        return payload
    if fixture_only:
        seed = resolve_self_seed()
        payload = {
            "schema_version": "cento.ai_self_improvement_e2e.source.v1",
            "status": "ready",
            "source": "fixture_seed_without_latest",
            "path": seed.get("path", ""),
            "request": seed.get("request") if isinstance(seed.get("request"), dict) else {},
            "source_payload": seed.get("source_payload") if isinstance(seed.get("source_payload"), dict) else {},
            "planning_loop": {"status": "skipped_fixture_only"},
            "written_at": now_iso(),
        }
        write_json(run_dir / "self_improve_source.json", payload)
        return payload

    planning_run_dir = SELF_IMPROVE_RUNS_ROOT / f"{run_dir.name}-planning"
    command = [
        "./scripts/cento.sh",
        "parallel-delivery",
        "self-improve",
        "run",
        "--run-dir",
        rel(planning_run_dir),
        "--quiet",
        "--json",
    ]
    proc = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    latest_payload = read_json(latest_next)
    payload = {
        "schema_version": "cento.ai_self_improvement_e2e.source.v1",
        "status": "ready" if latest_payload else "blocked",
        "source": "planning_loop_generated_latest" if latest_payload else "planning_loop_failed_without_next_cycle_request",
        "path": rel(latest_next) if latest_payload else "",
        "request": latest_payload,
        "planning_loop": {
            "status": "completed" if proc.returncode == 0 else "blocked",
            "command": command,
            "exit_code": proc.returncode,
            "stdout_tail": proc.stdout[-4000:],
            "stderr_tail": proc.stderr[-4000:],
            "run_dir": rel(planning_run_dir),
        },
        "written_at": now_iso(),
    }
    write_json(run_dir / "self_improve_source.json", payload)
    return payload


def patch_swarm_spend_summary(run_dir: Path) -> dict[str, Any]:
    rows = jsonl_rows(run_dir / "candidate_spend_ledger.jsonl")
    provider_counts = Counter(str(item.get("provider") or "unknown") for item in rows)
    provider_costs = {
        provider: round(sum(float(item.get("cost_usd_estimate") or 0.0) for item in rows if str(item.get("provider") or "unknown") == provider), 6)
        for provider in sorted(provider_counts)
    }
    return {
        "schema_version": "cento.ai_self_improvement_e2e.spend_summary.v1",
        "patch_swarm_run_id": run_dir.name,
        "candidate_rows": len(rows),
        "total_estimated_spend_usd": round(sum(float(item.get("cost_usd_estimate") or 0.0) for item in rows), 6),
        "provider_counts": dict(sorted(provider_counts.items())),
        "provider_costs_usd": provider_costs,
        "usage_guard": rel(run_dir / "usage_guard.json") if (run_dir / "usage_guard.json").exists() else "",
        "provider_usage": rel(run_dir / "provider_usage.jsonl") if (run_dir / "provider_usage.jsonl").exists() else "",
        "candidate_spend_ledger": rel(run_dir / "candidate_spend_ledger.jsonl") if (run_dir / "candidate_spend_ledger.jsonl").exists() else "",
        "written_at": now_iso(),
    }


def auto_merge_environment_blocked(receipt: dict[str, Any]) -> bool:
    if receipt.get("status") != "blocked" or receipt.get("push_requested"):
        return False
    blockers = {str(item) for item in receipt.get("blockers") or []}
    environment_prefixes = ("current_branch_not_",)
    environment_blockers = {"main_worktree_dirty", "integration_worktree_missing", "integration_branch_missing"}
    return bool(blockers) and all(item in environment_blockers or item.startswith(environment_prefixes) for item in blockers)


def run_self_e2e_auto_merge_gate(factory_run_dir: Path) -> dict[str, Any]:
    command = [
        "./scripts/cento.sh",
        "factory",
        "merge",
        rel(factory_run_dir),
        "--auto-merge-main",
        "--dry-run",
        "--json",
    ]
    proc = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    try:
        receipt = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        receipt = {}
    return {
        "schema_version": "cento.ai_self_improvement_e2e.auto_merge_gate.v1",
        "status": receipt.get("status", "blocked"),
        "command": command,
        "exit_code": proc.returncode,
        "dry_run": True,
        "push_requested": bool(receipt.get("push_requested", False)),
        "receipt": receipt,
        "receipt_path": rel(factory_run_dir / "integration" / "merge-receipt.json"),
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
        "written_at": now_iso(),
    }


def safe_integrator_apply_summary(factory_run_dir: Path, promotion: dict[str, Any]) -> dict[str, Any]:
    integration_dir = factory_run_dir / "integration"
    applied = read_json(integration_dir / "applied-patches.json")
    rejected = read_json(integration_dir / "rejected-patches.json")
    return {
        "schema_version": "cento.ai_self_improvement_e2e.safe_integrator_apply.v1",
        "status": "applied" if int(promotion.get("applied_count") or 0) > 0 else str(promotion.get("status") or "ready_for_apply"),
        "apply_requested": bool(promotion.get("apply")),
        "factory_run_dir": rel(factory_run_dir),
        "apply_plan": rel(integration_dir / "apply-plan.json") if (integration_dir / "apply-plan.json").exists() else "",
        "validation_fanout": rel(integration_dir / "validation-fanout.json") if (integration_dir / "validation-fanout.json").exists() else "",
        "applied_patches": rel(integration_dir / "applied-patches.json") if applied else "",
        "rejected_patches": rel(integration_dir / "rejected-patches.json") if rejected else "",
        "applied_count": len(applied.get("patches") or []),
        "rejected_count": len(rejected.get("patches") or []),
        "release_candidate": str(promotion.get("release_candidate") or ""),
        "written_at": now_iso(),
    }


def self_e2e_validation_summary(
    run_dir: Path,
    *,
    source: dict[str, Any],
    patch_receipt: dict[str, Any],
    integration: dict[str, Any],
    patch_validation: dict[str, Any],
    promotion: dict[str, Any],
    safe_apply: dict[str, Any],
    auto_gate: dict[str, Any],
    status: str,
) -> dict[str, Any]:
    checks = [
        {"name": "self_improve_source", "status": "passed" if source.get("status") == "ready" else "failed", "detail": source.get("source", "")},
        {"name": "patch_swarm_candidates", "status": "passed" if patch_receipt.get("status") == "candidates_generated" else "failed", "detail": str(patch_receipt.get("errors") or "")},
        {"name": "patch_swarm_integration", "status": "passed" if integration.get("status") == "completed" else "failed", "detail": str(integration.get("blockers") or "")},
        {"name": "patch_swarm_validation", "status": "passed" if patch_validation.get("status") == "passed" else "failed", "detail": patch_validation.get("status", "")},
        {"name": "factory_promotion", "status": "passed" if promotion.get("status") in {"ready_for_apply", "release_candidate_ready", "planned"} else "failed", "detail": str(promotion.get("status") or "")},
        {"name": "safe_integrator_apply", "status": "passed" if safe_apply.get("status") in {"ready_for_apply", "applied", "release_candidate_ready"} else "failed", "detail": str(safe_apply.get("status") or "")},
        {"name": "auto_merge_gate_no_push", "status": "passed" if not auto_gate or auto_gate.get("push_requested") is False else "failed", "detail": str(auto_gate.get("status") or "skipped")},
    ]
    return {
        "schema_version": SCHEMA_SELF_E2E_VALIDATION,
        "run_id": run_dir.name,
        "status": "passed" if status in {"ready_for_apply", "applied", "auto_merge_blocked_by_environment"} else "blocked",
        "e2e_status": status,
        "checks": checks,
        "written_at": now_iso(),
    }


def write_self_e2e_handoff(run_dir: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# AI Self-Improvement Autopilot E2E Handoff",
        "",
        f"- Run: `{payload.get('run_id')}`",
        f"- Status: `{payload.get('status')}`",
        f"- Patch Swarm: `{payload.get('patch_swarm_run_dir')}`",
        f"- Factory run: `{payload.get('factory_run_dir') or '-'}`",
        f"- Spend summary: `{rel(run_dir / 'spend_summary.json')}`",
        f"- Validation: `{rel(run_dir / 'validation_summary.json')}`",
        f"- Auto-merge gate: `{rel(run_dir / 'auto_merge_gate.json')}`",
        "",
        "No merge or push to main was performed. The auto-merge gate is dry-run only.",
        "",
    ]
    (run_dir / "handoff.md").write_text("\n".join(lines), encoding="utf-8")


def command_plan(args: argparse.Namespace) -> int:
    run_dir = resolve_run_dir(args.run_dir, create=True)
    manifest = write_plan(run_dir)
    write_demo_workset(run_dir)
    result = {"status": "planned", "run_dir": rel(run_dir), "implementation_manifest": rel(run_dir / "implementation_manifest.json"), "pass_count": len(manifest["hard_proreq_passes"])}
    print(json.dumps(result, indent=2) if args.json else f"planned {rel(run_dir)}")
    return 0


def command_execute(args: argparse.Namespace) -> int:
    run_dir = resolve_run_dir(args.run_dir, create=True)
    manifest = read_json(run_dir / "implementation_manifest.json") or write_plan(run_dir)
    passes = manifest.get("hard_proreq_passes") if isinstance(manifest.get("hard_proreq_passes"), list) else []
    if args.only:
        wanted = set(args.only.split(","))
        passes = [item for item in passes if item.get("id") in wanted]
    if args.max_passes:
        passes = passes[: args.max_passes]
    records: list[dict[str, Any]] = []
    for index, pass_spec in enumerate(passes, start=1):
        print(f"parallel-delivery proreq {index}/{len(passes)} {pass_spec['id']}", flush=True)
        record = execute_proreq_pass(pass_spec, args)
        records.append(record)
        partial = {
            "schema_version": SCHEMA_RECEIPT,
            "written_at": now_iso(),
            "status": "running",
            "run_dir": rel(run_dir),
            "expected_pass_count": len(passes),
            "total_workstream_count": len(WORKSTREAMS),
            "selected_pass_ids": [str(item.get("id") or "") for item in passes],
            "demo_required": not args.skip_demo,
            "passes": records,
        }
        write_json(run_dir / "proreq_receipt.partial.json", partial)
        if args.sleep_seconds > 0 and index < len(passes):
            time.sleep(args.sleep_seconds)
    demo_receipt = None
    if not args.skip_demo:
        print("parallel-delivery demo", flush=True)
        demo_receipt = run_demo(run_dir, execute=True)
    all_completed = bool(records) and all(item.get("status") == "completed" and item.get("workset_check", {}).get("status") == "passed" for item in records)
    if demo_receipt and demo_receipt.get("status") != "completed":
        all_completed = False
    receipt = {
        "schema_version": SCHEMA_RECEIPT,
        "written_at": now_iso(),
        "status": "completed" if all_completed else "failed",
        "run_dir": rel(run_dir),
        "implementation_manifest": rel(run_dir / "implementation_manifest.json"),
        "expected_pass_count": len(passes),
        "total_workstream_count": len(WORKSTREAMS),
        "selected_pass_ids": [str(item.get("id") or "") for item in passes],
        "demo_required": not args.skip_demo,
        "live_policy": {
            "openai_api_key_present": bool(os.environ.get("OPENAI_API_KEY")),
            "live_pro_requested": bool(args.live_pro),
            "reference_screenshot": args.reference_screenshot,
        },
        "passes": records,
        "demo_receipt": rel(run_dir / "demo" / "demo_receipt.json") if demo_receipt else "",
    }
    write_json(run_dir / "proreq_receipt.json", receipt)
    compose_execution_manifest(run_dir, receipt, demo_receipt)
    validation = validate_run(run_dir)
    result = {"status": receipt["status"], "run_dir": rel(run_dir), "receipt": rel(run_dir / "proreq_receipt.json"), "validation": validation["status"]}
    print(json.dumps(result, indent=2) if args.json else f"{receipt['status']} {rel(run_dir)}")
    return 0 if receipt["status"] == "completed" and validation["status"] == "passed" else 1


def command_demo(args: argparse.Namespace) -> int:
    run_dir = resolve_run_dir(args.run_dir, create=True)
    if not (run_dir / "implementation_manifest.json").exists():
        write_plan(run_dir)
    receipt = run_demo(run_dir, execute=not args.plan_only)
    print(json.dumps({"run_dir": rel(run_dir), "demo": receipt}, indent=2) if args.json else f"demo {receipt['status']} {rel(run_dir)}")
    return 0 if receipt["status"] in {"completed", "planned"} else 1


def command_validate(args: argparse.Namespace) -> int:
    run_dir = resolve_validation_run_dir(args.run_dir)
    payload = validate_selected_run(run_dir)
    print(json.dumps({"run_dir": rel(run_dir), **payload}, indent=2) if args.json else f"{payload['status']} {rel(run_dir)}")
    return 0 if payload["status"] == "passed" else 1


def command_status(args: argparse.Namespace) -> int:
    if getattr(args, "run", ""):
        run_root_value = Path(getattr(args, "run_root", "") or RUNS_ROOT)
        run_root = run_root_value if run_root_value.is_absolute() else ROOT / run_root_value
        run_dir = run_root / str(args.run)
    else:
        run_dir = resolve_validation_run_dir(args.run_dir)
    payload = status_for_selected_run(run_dir)
    print(json.dumps(payload, indent=2) if args.json else f"{payload['status']} {payload['validation']} {payload['run_dir']}")
    return 0


def command_train_plan(args: argparse.Namespace) -> int:
    run_dir = resolve_train_run_dir(args.run_id, create=True)
    source = Path(args.workset)
    if not source.is_absolute():
        source = ROOT / source
    manifest = build_train_artifacts(source, run_dir, max_parallel=args.max_parallel)
    payload = {
        "status": manifest.get("status"),
        "run_id": run_dir.name,
        "run_dir": rel(run_dir),
        "train_manifest": rel(run_dir / "train_manifest.json"),
        "integration_queue": rel(run_dir / "integration_queue.json"),
        "decision_report": rel(run_dir / "decision_report.md"),
    }
    print(json.dumps(payload, indent=2) if args.json else f"{payload['status']} {payload['run_dir']}")
    return 0 if manifest.get("status") == "planned" else 1


def command_train_run(args: argparse.Namespace) -> int:
    simulate = bool(getattr(args, "simulate", False))
    workset_execute = bool(getattr(args, "workset_execute", False))
    if not simulate and not workset_execute:
        print("parallel-delivery train run requires --simulate or --workset-execute.", file=sys.stderr)
        return 2
    run_dir = resolve_train_run_dir(args.run_id)
    if workset_execute:
        receipt = execute_train_workset(
            run_dir,
            runtime=getattr(args, "runtime", "fixture"),
            runtime_profile=getattr(args, "runtime_profile", "") or "",
            api_profile=getattr(args, "api_profile", "") or "",
            api_config=getattr(args, "api_config", "") or "",
            budget_usd=getattr(args, "budget_usd", None),
            max_budget_usd=getattr(args, "max_budget_usd", None),
            validation=getattr(args, "validation", "smoke") or "",
            worker_timeout=getattr(args, "worker_timeout", None),
            retry_attempts=getattr(args, "retry_attempts", None),
            fixture_case=getattr(args, "fixture_case", "valid") or "valid",
            allow_dirty_owned=bool(getattr(args, "allow_dirty_owned", False)),
            allow_creates=bool(getattr(args, "allow_creates", False)),
        )
    else:
        receipt = simulate_train_workers(run_dir)
    payload = {"run_id": run_dir.name, "run_dir": rel(run_dir), "receipt": rel(run_dir / "train_receipt.json"), **receipt}
    print(json.dumps(payload, indent=2) if args.json else f"{receipt['status']} {rel(run_dir)}")
    return 0 if receipt.get("status") in {"workers_simulated", "workset_completed"} else 1


def command_train_integrate(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("parallel-delivery train integrate v1 requires --dry-run; patch apply is not implemented in this MVP.", file=sys.stderr)
        return 2
    run_dir = resolve_train_run_dir(args.run_id)
    receipt = dry_run_train_integration(run_dir)
    payload = {"run_id": run_dir.name, "run_dir": rel(run_dir), "receipt": rel(run_dir / "train_receipt.json"), **receipt}
    print(json.dumps(payload, indent=2) if args.json else f"{receipt['status']} {rel(run_dir)}")
    return 0 if receipt.get("status") == "integration_planned" else 1


def command_train_status(args: argparse.Namespace) -> int:
    run_dir = resolve_train_run_dir(args.run_id)
    manifest = read_json(run_dir / "train_manifest.json")
    receipt = read_json(run_dir / "train_receipt.json")
    validation = read_json(run_dir / "validation_summary.json")
    queue = read_json(run_dir / "integration_queue.json")
    promotion = read_json(run_dir / "promotion_decision.json")
    items = queue.get("items") if isinstance(queue.get("items"), list) else []
    payload = {
        "run_id": run_dir.name,
        "run_dir": rel(run_dir),
        "status": receipt.get("status") or manifest.get("status", "unknown"),
        "validation": validation.get("status", "unknown"),
        "max_parallel": manifest.get("max_parallel", 0),
        "queue_count": len(items),
        "train_manifest": rel(run_dir / "train_manifest.json"),
        "decision_report": rel(run_dir / "decision_report.md"),
        "workset_receipt": receipt.get("workset_receipt", ""),
        "promotion": promotion.get("decision", "unknown"),
        "factory_run_dir": promotion.get("factory_run_dir", ""),
    }
    print(json.dumps(payload, indent=2) if args.json else f"{payload['status']} {payload['validation']} {payload['run_dir']}")
    return 0


def command_train_validate(args: argparse.Namespace) -> int:
    run_dir = resolve_train_run_dir(args.run_id)
    payload = validate_train_run(run_dir)
    result = {"run_id": run_dir.name, "run_dir": rel(run_dir), **payload}
    print(json.dumps(result, indent=2) if args.json else f"{payload['status']} {rel(run_dir)}")
    return 0 if payload["status"] == "passed" else 1


def command_train_promote(args: argparse.Namespace) -> int:
    if getattr(args, "apply", False) and getattr(args, "dry_run", False):
        print("parallel-delivery train promote accepts either --dry-run or --apply, not both.", file=sys.stderr)
        return 2
    run_dir = resolve_train_run_dir(args.run_id)
    decision = promote_train_run(
        run_dir,
        apply=bool(getattr(args, "apply", False)),
        validate_each=bool(getattr(args, "validate_each", False)),
        branch=getattr(args, "branch", "") or "",
        worktree=getattr(args, "worktree", "") or "",
        limit=int(getattr(args, "limit", 0) or 0),
    )
    payload = {"run_id": run_dir.name, "run_dir": rel(run_dir), **decision}
    print(json.dumps(payload, indent=2) if args.json else f"{decision['status']} {decision['decision']} {rel(run_dir)}")
    return 0 if decision.get("status") in {"planned", "completed"} else 1


def command_train_e2e(args: argparse.Namespace) -> int:
    if getattr(args, "apply", False) and getattr(args, "dry_run", False):
        print("parallel-delivery train e2e accepts either --dry-run or --apply, not both.", file=sys.stderr)
        return 2
    run_id = args.run_id or f"train-e2e-{now_stamp()}"
    run_dir = resolve_train_run_dir(run_id, create=True)
    source = Path(args.workset)
    if not source.is_absolute():
        source = ROOT / source
    manifest = build_train_artifacts(source, run_dir, max_parallel=args.max_parallel)
    receipt: dict[str, Any] = {}
    validation: dict[str, Any] = {}
    promotion: dict[str, Any] = {}
    if manifest.get("status") == "planned":
        receipt = execute_train_workset(
            run_dir,
            runtime=getattr(args, "runtime", "fixture"),
            runtime_profile=getattr(args, "runtime_profile", "") or "",
            api_profile=getattr(args, "api_profile", "") or "",
            api_config=getattr(args, "api_config", "") or "",
            budget_usd=getattr(args, "budget_usd", None),
            max_budget_usd=getattr(args, "max_budget_usd", None),
            validation=getattr(args, "validation", "smoke") or "",
            worker_timeout=getattr(args, "worker_timeout", None),
            retry_attempts=getattr(args, "retry_attempts", None),
            fixture_case=getattr(args, "fixture_case", "valid") or "valid",
            allow_dirty_owned=bool(getattr(args, "allow_dirty_owned", False)),
            allow_creates=bool(getattr(args, "allow_creates", False)),
        )
        validation = validate_train_run(run_dir)
        if receipt.get("status") == "workset_completed":
            promotion = promote_train_run(
                run_dir,
                apply=bool(getattr(args, "apply", False)),
                validate_each=bool(getattr(args, "validate_each", False)),
                branch=getattr(args, "branch", "") or "",
                worktree=getattr(args, "worktree", "") or "",
                limit=int(getattr(args, "limit", 0) or 0),
            )
    status = "completed" if promotion.get("status") in {"planned", "completed"} and validation.get("status") == "passed" else "blocked"
    payload = {
        "status": status,
        "run_id": run_dir.name,
        "run_dir": rel(run_dir),
        "train_manifest": rel(run_dir / "train_manifest.json"),
        "workset_receipt": receipt.get("workset_receipt", ""),
        "validation": validation.get("status", "unknown"),
        "promotion": promotion.get("decision", "unknown"),
        "factory_run_dir": promotion.get("factory_run_dir", ""),
        "promotion_decision": rel(run_dir / "promotion_decision.json") if (run_dir / "promotion_decision.json").exists() else "",
        "release_candidate": promotion.get("release_candidate", ""),
    }
    print(json.dumps(payload, indent=2) if args.json else f"{status} {payload['promotion']} {rel(run_dir)}")
    return 0 if status == "completed" else 1


def command_patch_swarm_plan(args: argparse.Namespace) -> int:
    run_id = args.run_id or f"patch-swarm-{now_stamp()}"
    run_dir = resolve_patch_swarm_run_dir(run_id, create=True)
    manifest = build_patch_swarm_plan(
        run_dir,
        objective=getattr(args, "objective", "") or PATCH_SWARM_OBJECTIVE,
        candidate_target=getattr(args, "candidate_target", 100),
        max_parallel_agents=getattr(args, "max_parallel_agents", 5),
        providers=patch_swarm_provider_list(getattr(args, "providers", "")),
        live=bool(getattr(args, "live", False)),
    )
    payload = {
        "status": manifest.get("status"),
        "run_id": run_dir.name,
        "run_dir": rel(run_dir),
        "candidate_target": manifest.get("candidate_target"),
        "proreq_execution_count": manifest.get("proreq_execution_count"),
        "manifest": rel(run_dir / "patch_swarm_manifest.json"),
        "ui_state": rel(run_dir / "ui_state.json"),
    }
    print(json.dumps(payload, indent=2) if args.json else f"{payload['status']} {payload['run_dir']}")
    return 0


def command_patch_swarm_split(args: argparse.Namespace) -> int:
    payload, code = planner_tool.run_from_args(args, command="parallel-delivery patch-swarm split")
    if args.json:
        print(planner_tool.stable_json_dumps(payload), end="")
    elif payload.get("ok"):
        print(f"{payload.get('state')} {payload.get('candidate_count')} tasks {payload.get('run_dir')}")
    else:
        print("; ".join(payload.get("errors", ["split plan failed"])), file=sys.stderr)
    return code


def command_patch_swarm_leases(args: argparse.Namespace) -> int:
    payload, code = lease_tool.run_create(args, command="parallel-delivery patch-swarm leases")
    if args.json:
        print(lease_tool.stable_json_dumps(payload), end="")
    elif payload.get("ok"):
        print(f"leases {payload.get('run_id')} {payload.get('run_dir')}")
    else:
        print("; ".join(payload.get("errors", ["lease generation failed"])), file=sys.stderr)
    return code


def command_patch_swarm_validate_leases(args: argparse.Namespace) -> int:
    payload, code = lease_tool.run_validate(args)
    if args.json:
        print(lease_tool.stable_json_dumps(payload), end="")
    elif payload.get("ok"):
        print(f"lease validation passed {payload.get('run_id')} {payload.get('run_dir', '')}")
    else:
        print("; ".join(payload.get("errors", ["lease validation failed"])), file=sys.stderr)
    return code


def command_patch_bundles_validate(args: argparse.Namespace) -> int:
    payload, code = patch_bundles_tool.run_validate_from_args(args)
    if args.json:
        print(patch_bundles_tool.stable_json_dumps(payload), end="")
    elif payload.get("validation_status") == "accepted":
        print(f"accepted {payload.get('bundle_id')} {payload.get('receipt_id')}")
    else:
        print("; ".join(payload.get("reason_codes") or ["patch bundle rejected"]), file=sys.stderr)
    return code


def command_patch_bundles_collect(args: argparse.Namespace) -> int:
    payload, code = patch_bundles_tool.run_collect_from_args(args)
    if args.json:
        print(patch_bundles_tool.stable_json_dumps(payload), end="")
    else:
        print(
            "patch bundles "
            f"accepted={payload.get('accepted_count')} "
            f"rejected={payload.get('rejected_count')} "
            f"report={Path(args.out) / 'patch-bundle-report.json'}"
        )
    return code


def command_patch_swarm_prompts(args: argparse.Namespace) -> int:
    payload, code = prompts_tool.run_generate_from_args(args, command="parallel-delivery patch-swarm prompts")
    if args.json:
        print(prompts_tool.stable_json_dumps(payload), end="")
    elif payload.get("ok"):
        print(f"{payload.get('state')} {payload.get('prompt_count')} prompts {payload.get('run_dir')}")
    else:
        print("; ".join(payload.get("errors", ["prompt bundle failed"])), file=sys.stderr)
    return code


def command_patch_swarm_worker_packets(args: argparse.Namespace) -> int:
    try:
        if getattr(args, "fixture", False):
            result = codex_packets_tool.build_codex_packets_fixture(
                Path(args.run_dir),
                run_id=args.run_id or "codex-packets-fixture",
                count=int(args.count or codex_packets_tool.DEFAULT_PACKET_COUNT),
                timestamp=args.fixed_timestamp or "2026-01-01T00:00:00Z",
            )
        else:
            result = codex_packets_tool.write_packet_bundle(
                codex_packets_tool.CodexPacketRequest(
                    run_id=args.run_id,
                    run_dir=Path(args.run_dir),
                    count=args.count,
                    fixed_timestamp=args.fixed_timestamp or None,
                )
            )
        payload = codex_packets_tool.result_payload(result)
        code = 0 if payload.get("ok") else 1
    except codex_packets_tool.CodexPacketError as exc:
        payload = {
            "ok": False,
            "run_id": args.run_id or Path(args.run_dir).name,
            "packet_count": 0,
            "errors": [str(exc)],
            "warnings": [],
        }
        code = 1
    if args.json:
        print(codex_packets_tool.stable_json_dumps(payload), end="")
    elif payload.get("ok"):
        print(f"codex packets {payload.get('packet_count')} {payload.get('run_dir')}")
    else:
        print("; ".join(payload.get("errors", ["worker packet generation failed"])), file=sys.stderr)
    return code


def command_patch_swarm_dispatch(args: argparse.Namespace) -> int:
    payload = worker_status_tool.plan_dispatch(
        Path(args.run_dir),
        run_id=getattr(args, "run_id", "") or None,
        candidate_target=int(getattr(args, "candidate_target", worker_status_tool.MAX_CANDIDATE_TASKS) or worker_status_tool.MAX_CANDIDATE_TASKS),
        max_parallel_agents=int(getattr(args, "max_parallel_agents", 5) or 5),
        dry_run=bool(getattr(args, "dry_run", True)),
        live=bool(getattr(args, "live", False)),
        timestamp=getattr(args, "fixed_timestamp", "") or None,
        fixture=bool(getattr(args, "fixture", False)),
    )
    code = 0 if payload.get("ok") else 1
    if args.json:
        print(worker_status_tool.stable_json_dumps(payload), end="")
    elif payload.get("ok"):
        print(f"worker dispatch dry-run {payload.get('candidate_tasks')} tasks {payload.get('run_dir')}")
    else:
        print("; ".join(payload.get("errors", ["worker dispatch planning failed"])), file=sys.stderr)
    return code


def command_patch_swarm_worker_status(args: argparse.Namespace) -> int:
    try:
        payload = worker_status_tool.status_for_run(Path(args.run_dir))
        code = 0 if payload.get("ok") else 1
    except worker_status_tool.WorkerStatusError as exc:
        payload = {
            "ok": False,
            "run_id": Path(args.run_dir).name,
            "run_dir": args.run_dir,
            "errors": [str(exc)],
            "warnings": [],
        }
        code = 1
    if args.json:
        print(worker_status_tool.stable_json_dumps(payload), end="")
    elif payload.get("ok"):
        print(f"worker status {payload.get('candidate_tasks')} tasks {payload.get('run_dir')}")
    else:
        print("; ".join(payload.get("errors", ["worker status unavailable"])), file=sys.stderr)
    return code


def command_release_candidate_create(args: argparse.Namespace) -> int:
    payload, code = release_candidate_tool.run_create_from_args(args)
    if args.json:
        print(release_candidate_tool.stable_json_dumps(payload), end="")
    elif payload.get("ok"):
        print(f"{payload.get('status')} {payload.get('release_candidate') or payload.get('out')}")
    else:
        print(str(payload.get("error") or "release candidate creation failed"), file=sys.stderr)
    return code


def command_taskstream_emit(args: argparse.Namespace) -> int:
    payload, code = taskstream_tool.run_emit_from_args(args)
    if args.json:
        print(taskstream_tool.stable_json_dumps(payload), end="")
    elif code == 0:
        print(
            "taskstream handoff "
            f"tasks={payload.get('task_count')} "
            f"agent_work={payload.get('agent_work_routed_count')} "
            f"manifest_only={payload.get('manifest_only_count')} "
            f"report={Path(args.out) / 'taskstream-handoff-report.json'}"
        )
    else:
        print("; ".join(payload.get("errors", ["taskstream emit failed"])), file=sys.stderr)
    return code


def command_taskstream_preflight(args: argparse.Namespace) -> int:
    payload, code = taskstream_tool.run_preflight_from_args(args)
    if args.json:
        print(taskstream_tool.stable_json_dumps(payload), end="")
    elif code == 0:
        print(f"taskstream preflight passed {payload.get('manifest_dir')}")
    else:
        print("; ".join(payload.get("errors") or ["taskstream preflight blocked"]), file=sys.stderr)
    return code


def command_taskstream_apply(args: argparse.Namespace) -> int:
    payload, code = taskstream_tool.run_apply_from_args(args)
    if args.json:
        print(taskstream_tool.stable_json_dumps(payload), end="")
    elif code == 0:
        print(f"taskstream apply receipts={len(payload.get('receipts') or [])}")
    else:
        print("; ".join(payload.get("errors", ["taskstream apply failed"])), file=sys.stderr)
    return code


def command_patch_swarm_execute(args: argparse.Namespace) -> int:
    run_dir = resolve_patch_swarm_run_dir(args.run_id)
    receipt = execute_patch_swarm(
        run_dir,
        fixture=bool(getattr(args, "fixture", False) or not getattr(args, "live", False)),
        budget_cap_usd=getattr(args, "budget_cap_usd", None),
        max_budget_usd=getattr(args, "max_budget_usd", None),
        api_sandbox_candidates=int(getattr(args, "api_sandbox_candidates", 1) or 0),
        api_profile=getattr(args, "api_profile", PATCH_SWARM_API_PROFILE),
        api_config=getattr(args, "api_config", str(ROOT / ".cento" / "api_workers.yaml")),
    )
    payload = {"run_id": run_dir.name, "run_dir": rel(run_dir), **receipt}
    print(json.dumps(payload, indent=2) if args.json else f"{receipt.get('status')} {rel(run_dir)}")
    return 0 if receipt.get("status") == "candidates_generated" else 1


def command_patch_swarm_integrate(args: argparse.Namespace) -> int:
    run_dir = resolve_patch_swarm_run_dir(args.run_id)
    integration = integrate_patch_swarm(
        run_dir,
        apply=bool(getattr(args, "apply", False)),
        factory_run=getattr(args, "factory_run", ""),
        validate_each=bool(getattr(args, "validate_each", False)),
        branch=getattr(args, "branch", ""),
        worktree=getattr(args, "worktree", ""),
        limit=int(getattr(args, "limit", 0) or 0),
    )
    payload = {"run_id": run_dir.name, "run_dir": rel(run_dir), **integration}
    print(json.dumps(payload, indent=2) if args.json else f"{integration.get('status')} {rel(run_dir)}")
    return 0 if integration.get("status") == "completed" else 1


def command_patch_swarm_validate(args: argparse.Namespace) -> int:
    run_dir = resolve_patch_swarm_run_dir(args.run_id)
    validation = validate_patch_swarm_run(run_dir)
    payload = {"run_id": run_dir.name, "run_dir": rel(run_dir), **validation}
    print(json.dumps(payload, indent=2) if args.json else f"{validation.get('status')} {rel(run_dir)}")
    return 0 if validation.get("status") == "passed" else 1


def command_patch_swarm_status(args: argparse.Namespace) -> int:
    console_mode = bool(
        getattr(args, "run_dir", "")
        or getattr(args, "output_dir", "")
        or getattr(args, "write_html", False)
        or getattr(args, "strict_links", False)
        or (getattr(args, "run_id", "") and ("/" in getattr(args, "run_id", "") or "\\" in getattr(args, "run_id", "")))
    )
    if console_mode:
        raw_run_dir = getattr(args, "run_dir", "") or ""
        if raw_run_dir:
            run_dir = Path(raw_run_dir)
        elif getattr(args, "run_id", "") and ("/" in args.run_id or "\\" in args.run_id):
            run_dir = Path(args.run_id)
        elif getattr(args, "run_id", ""):
            run_dir = resolve_patch_swarm_run_dir(args.run_id)
        else:
            run_dir = latest_patch_swarm_fixture_e2e_run_dir() or patch_swarm_latest_run_dir() or RUNS_ROOT
        output_dir = Path(args.output_dir) if getattr(args, "output_dir", "") else None
        try:
            console_data, metadata = patch_swarm_console_tool.render_console(
                run_dir,
                output_dir=output_dir,
                write_html=bool(getattr(args, "write_html", False)),
                strict_links=bool(getattr(args, "strict_links", False)),
            )
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        if args.json:
            print(
                patch_swarm_console_tool.stable_json(
                    patch_swarm_console_tool.emit_console_json(console_data, output_dir=output_dir or run_dir),
                    pretty=False,
                ),
                end="",
            )
        else:
            target = metadata.get("start_here") or metadata.get("console_data") or console_data.run_dir
            print(f"{console_data.current_run.get('result', 'unknown')} {console_data.candidate_count} candidates {target}")
        return 0

    run_dir = resolve_patch_swarm_run_dir(args.run_id)
    manifest = read_json(run_dir / "patch_swarm_manifest.json")
    receipt = read_json(run_dir / "patch_swarm_receipt.json")
    integration = read_json(run_dir / "integration_execution" / "integration_execution.json")
    validation = read_json(run_dir / "validation_summary.json")
    ui_state = read_json(run_dir / "ui_state.json")
    payload = {
        "schema_version": "cento.patch_swarm.status.v1",
        "run_id": run_dir.name,
        "run_dir": rel(run_dir),
        "status": validation.get("status") or integration.get("status") or receipt.get("status") or manifest.get("status", "unknown"),
        "candidate_target": manifest.get("candidate_target", 0),
        "candidate_count": receipt.get("candidate_count", 0),
        "proreq_execution_count": manifest.get("proreq_execution_count", 0),
        "selected_count": integration.get("selected_count", 0),
        "providers": manifest.get("providers", []),
        "estimated_cost_usd": receipt.get("estimated_cost_usd", 0.0),
        "validation": validation.get("status", "unknown"),
        "ui_state": rel(run_dir / "ui_state.json") if ui_state else "",
        "decision_report": rel(run_dir / "decision_report.md") if (run_dir / "decision_report.md").exists() else "",
    }
    print(json.dumps(payload, indent=2) if args.json else f"{payload['status']} {payload['candidate_count']} candidates {payload['run_dir']}")
    return 0


def command_patch_swarm_e2e(args: argparse.Namespace) -> int:
    if hasattr(args, "run_root") and not bool(getattr(args, "live", False)) and not bool(getattr(args, "apply", False)):
        payload, code = validation_e2e_tool.run_from_args(args, command="parallel-delivery patch-swarm e2e")
        if args.json:
            print(validation_e2e_tool.stable_json_dumps(payload), end="")
        elif payload.get("ok"):
            print(f"{payload.get('state')} {payload.get('candidate_count')} tasks {payload.get('run_dir')}")
        else:
            print("; ".join(payload.get("errors", ["fixture e2e failed"])), file=sys.stderr)
        return code

    run_id = args.run_id or f"patch-swarm-e2e-{now_stamp()}"
    run_dir = resolve_patch_swarm_run_dir(run_id, create=True)
    planner_fixture_dir = run_dir.parent.parent / "planner-fixture"
    planner_payload, planner_code = planner_tool.run_planner_command(
        candidate_target=int(getattr(args, "candidate_target", 100) or 100),
        command="parallel-delivery patch-swarm e2e",
        dry_run=False,
        live_pro=bool(getattr(args, "live", False)),
        max_parallel_agents=int(getattr(args, "max_parallel_agents", 5) or 5),
        mode="fixture" if bool(getattr(args, "fixture", False) or not getattr(args, "live", False)) else "no-model",
        request_text=getattr(args, "objective", "") or PATCH_SWARM_OBJECTIVE,
        run_dir=planner_fixture_dir,
        run_id="planner-fixture",
    )
    if planner_code != 0:
        payload = {
            "status": "blocked",
            "run_id": run_dir.name,
            "run_dir": rel(run_dir),
            "planner": planner_payload,
            "errors": planner_payload.get("errors", []),
        }
        print(json.dumps(payload, indent=2) if args.json else f"blocked {rel(run_dir)}")
        return planner_code
    manifest = build_patch_swarm_plan(
        run_dir,
        objective=getattr(args, "objective", "") or PATCH_SWARM_OBJECTIVE,
        candidate_target=getattr(args, "candidate_target", 100),
        max_parallel_agents=getattr(args, "max_parallel_agents", 5),
        providers=patch_swarm_provider_list(getattr(args, "providers", "")),
        live=bool(getattr(args, "live", False)),
    )
    receipt = execute_patch_swarm(
        run_dir,
        fixture=bool(getattr(args, "fixture", False) or not getattr(args, "live", False)),
        budget_cap_usd=getattr(args, "budget_cap_usd", None),
        max_budget_usd=getattr(args, "max_budget_usd", None),
        api_sandbox_candidates=int(getattr(args, "api_sandbox_candidates", 1) or 0),
        api_profile=getattr(args, "api_profile", PATCH_SWARM_API_PROFILE),
        api_config=getattr(args, "api_config", str(ROOT / ".cento" / "api_workers.yaml")),
    )
    integration: dict[str, Any] = {}
    validation: dict[str, Any] = {}
    if receipt.get("status") == "candidates_generated":
        integration = integrate_patch_swarm(
            run_dir,
            apply=bool(getattr(args, "apply", False)),
            factory_run=getattr(args, "factory_run", ""),
            validate_each=bool(getattr(args, "validate_each", False)),
            branch=getattr(args, "branch", ""),
            worktree=getattr(args, "worktree", ""),
            limit=int(getattr(args, "limit", 0) or 0),
        )
        validation = validate_patch_swarm_run(run_dir)
    status = "completed" if validation.get("status") == "passed" and integration.get("status") == "completed" else "blocked"
    payload = {
        "status": status,
        "run_id": run_dir.name,
        "run_dir": rel(run_dir),
        "candidate_target": manifest.get("candidate_target"),
        "candidate_count": receipt.get("candidate_count", 0),
        "proreq_execution_count": manifest.get("proreq_execution_count"),
        "selected_count": integration.get("selected_count", 0),
        "estimated_cost_usd": receipt.get("estimated_cost_usd", 0.0),
        "validation": validation.get("status", "unknown"),
        "safe_integrator_handoff": integration.get("safe_integrator_handoff", ""),
        "ui_state": rel(run_dir / "ui_state.json"),
        "decision_report": rel(run_dir / "decision_report.md"),
        "planner": {
            "run_dir": planner_payload.get("run_dir", ""),
            "split_plan": "workspace/runs/parallel-delivery/planner-fixture/split-plan.json",
            "task_graph": "workspace/runs/parallel-delivery/planner-fixture/task-graph.json",
            "candidate_count": planner_payload.get("candidate_count", 0),
            "state": planner_payload.get("state", "unknown"),
        },
    }
    print(json.dumps(payload, indent=2) if args.json else f"{status} {payload['candidate_count']} candidates {rel(run_dir)}")
    return 0 if status == "completed" else 1


def command_self_improve_run(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    run_dir = resolve_self_run_dir(args.run_dir, create=True)
    seed = resolve_self_seed()
    manifest = {
        "schema_version": SCHEMA_SELF_MANIFEST,
        "cycle_id": run_dir.name,
        "created_at": now_iso(),
        "seed_source": seed.get("source"),
        "seed_path": seed.get("path"),
        "seed_objective": seed_objective(seed),
        "pass_count": 4,
        "budget": {
            "target_usd": AGENT_PREFERRED_COMPUTE_POLICY["target_spend_usd_max"],
            "hard_cap_usd": AGENT_PREFERRED_COMPUTE_POLICY["hard_spend_usd_max"],
        },
        "autonomy_mode": "plan_then_gate",
        "implementation_execution": "disabled",
        "scheduler": {
            "trigger": "manual" if not args.scheduler_trigger else args.scheduler_trigger,
            "cron_time": args.cron_time,
            "command": "cento parallel-delivery self-improve run --json",
        },
        "live_policy": {
            "live_pro_requested": bool(args.live_pro),
            "openai_api_key_present": bool(os.environ.get("OPENAI_API_KEY")),
            "image_requested": True,
            "image_failure_blocks_backend": False,
        },
        "compute_routing_policy": AGENT_PREFERRED_COMPUTE_POLICY,
    }
    write_self_json(run_dir, "nightly_cycle_manifest.json", manifest)
    pass_records: list[dict[str, Any]] = []
    for index, focus in enumerate(SELF_IMPROVE_PASS_FOCUS, start=1):
        if not args.quiet:
            print(f"self-improve pass {index}/4 {focus['id']}", flush=True)
        record = execute_self_improve_pass(index, focus, seed, pass_records, args)
        record["cycle_id"] = run_dir.name
        pass_records.append(record)
        write_self_json(run_dir, f"pass_{index:02d}_child_run_summary.json", record)
        if args.sleep_seconds > 0 and index < len(SELF_IMPROVE_PASS_FOCUS):
            time.sleep(args.sleep_seconds)

    preliminary_gates = self_improve_validation(run_dir)
    recommendation = promotion_recommendation(pass_records, preliminary_gates)
    metrics = loop_metrics_payload(run_dir, started, pass_records)
    next_request = next_cycle_request_payload(seed, pass_records, preliminary_gates, recommendation)
    handoff = evidence_handoff_payload(run_dir, pass_records, preliminary_gates, recommendation)
    write_self_json(run_dir, "loop_metrics.json", metrics)
    write_self_json(run_dir, "promotion_recommendation.json", recommendation)
    write_self_json(run_dir, "evidence_handoff.json", handoff)
    write_self_json(run_dir, "next_cycle_request.json", next_request)
    gates = self_improve_validation(run_dir)
    write_self_json(run_dir, "validation_gates.json", gates)
    if gates.get("status") != preliminary_gates.get("status"):
        recommendation = promotion_recommendation(pass_records, gates)
        handoff = evidence_handoff_payload(run_dir, pass_records, gates, recommendation)
        next_request = next_cycle_request_payload(seed, pass_records, gates, recommendation)
        write_self_json(run_dir, "promotion_recommendation.json", recommendation)
        write_self_json(run_dir, "evidence_handoff.json", handoff)
        write_self_json(run_dir, "next_cycle_request.json", next_request)
    payload = {
        "status": "completed" if gates.get("status") == "passed" else "blocked",
        "run_dir": rel(run_dir),
        "latest_dir": rel(self_latest_dir()),
        "validation": gates.get("status"),
        "promotion_recommendation": recommendation.get("recommendation"),
        "next_cycle_request": rel(run_dir / "next_cycle_request.json"),
    }
    print(json.dumps(payload, indent=2) if args.json else f"{payload['status']} {payload['validation']} {payload['run_dir']}")
    return 0 if gates.get("status") == "passed" else 1


def command_self_improve_e2e(args: argparse.Namespace) -> int:
    run_id = args.run_id or f"self-improve-e2e-{now_stamp()}"
    run_dir = resolve_self_e2e_run_dir(run_id, create=True)
    fixture_only = bool(getattr(args, "fixture_only", False))
    source = self_e2e_source_payload(run_dir, fixture_only=fixture_only)
    request = source.get("request") if isinstance(source.get("request"), dict) else {}
    objective = str(request.get("objective") or request.get("seed_objective") or PATCH_SWARM_OBJECTIVE)
    patch_run_dir = run_dir / f"patch-swarm-{run_dir.name}"
    factory_run_dir = FACTORY_RUNS_ROOT / f"ai-self-improvement-e2e-{run_dir.name}"
    manifest = {
        "schema_version": SCHEMA_SELF_E2E,
        "run_id": run_dir.name,
        "created_at": now_iso(),
        "status": "running",
        "source": rel(run_dir / "self_improve_source.json"),
        "candidate_target": int(getattr(args, "candidate_target", 30) or 30),
        "max_parallel_agents": int(getattr(args, "max_parallel_agents", 3) or 3),
        "budget_cap_usd": float(getattr(args, "budget_cap_usd", 1.0) or 0.0),
        "max_budget_usd": float(getattr(args, "max_budget_usd", 1.0) or 0.0),
        "fixture_only": fixture_only,
        "apply": bool(getattr(args, "apply", False)),
        "validate_each": bool(getattr(args, "validate_each", False)),
        "auto_merge_gate": bool(getattr(args, "auto_merge_gate", False)),
        "no_main_push": True,
        "artifacts": {
            "self_improve_source": rel(run_dir / "self_improve_source.json"),
            "patch_swarm_result": rel(run_dir / "patch_swarm_result.json"),
            "factory_promotion": rel(run_dir / "factory_promotion.json"),
            "safe_integrator_apply": rel(run_dir / "safe_integrator_apply.json"),
            "auto_merge_gate": rel(run_dir / "auto_merge_gate.json"),
            "spend_summary": rel(run_dir / "spend_summary.json"),
            "validation_summary": rel(run_dir / "validation_summary.json"),
            "handoff": rel(run_dir / "handoff.md"),
        },
    }
    write_json(run_dir / "e2e_manifest.json", manifest)

    patch_manifest: dict[str, Any] = {}
    patch_receipt: dict[str, Any] = {}
    integration: dict[str, Any] = {}
    patch_validation: dict[str, Any] = {}
    promotion: dict[str, Any] = {}
    safe_apply: dict[str, Any] = {}
    auto_gate: dict[str, Any] = {}
    status = "blocked"

    if source.get("status") == "ready":
        patch_manifest = build_patch_swarm_plan(
            patch_run_dir,
            objective=objective,
            candidate_target=int(getattr(args, "candidate_target", 30) or 30),
            max_parallel_agents=int(getattr(args, "max_parallel_agents", 3) or 3),
            providers=patch_swarm_provider_list(getattr(args, "providers", "")),
            live=not fixture_only,
        )
        retarget_patch_swarm_to_sandbox(patch_run_dir, run_dir / "sandbox")
        patch_receipt = execute_patch_swarm(
            patch_run_dir,
            fixture=fixture_only,
            budget_cap_usd=getattr(args, "budget_cap_usd", 1.0),
            max_budget_usd=getattr(args, "max_budget_usd", 1.0),
            api_sandbox_candidates=int(getattr(args, "api_sandbox_candidates", 1) or 0),
            api_profile=getattr(args, "api_profile", PATCH_SWARM_API_PROFILE),
            api_config=getattr(args, "api_config", str(ROOT / ".cento" / "api_workers.yaml")),
        )
        if patch_receipt.get("status") == "candidates_generated":
            integration = integrate_patch_swarm(
                patch_run_dir,
                apply=bool(getattr(args, "apply", False)),
                factory_run=rel(factory_run_dir),
                validate_each=bool(getattr(args, "validate_each", False)),
                branch=getattr(args, "branch", ""),
                worktree=getattr(args, "worktree", ""),
                limit=int(getattr(args, "limit", 1) or 0),
            )
            patch_validation = validate_patch_swarm_run(patch_run_dir)
            promotion = read_json(patch_run_dir / "factory_promotion.json")
            if promotion:
                factory_run_value = str(promotion.get("factory_run_dir") or rel(factory_run_dir))
                factory_run_dir = resolve_cento_path(factory_run_value)
                safe_apply = safe_integrator_apply_summary(factory_run_dir, promotion)
                if getattr(args, "auto_merge_gate", False):
                    auto_gate = run_self_e2e_auto_merge_gate(factory_run_dir)
                if auto_gate and auto_merge_environment_blocked(auto_gate.get("receipt") if isinstance(auto_gate.get("receipt"), dict) else {}):
                    status = "auto_merge_blocked_by_environment"
                elif safe_apply.get("status") == "applied":
                    status = "applied"
                elif promotion.get("status") == "ready_for_apply":
                    status = "ready_for_apply"
                elif promotion.get("status") == "release_candidate_ready":
                    status = "applied"
                else:
                    status = "blocked"

    spend = patch_swarm_spend_summary(patch_run_dir)
    write_json(run_dir / "patch_swarm_result.json", {"manifest": patch_manifest, "receipt": patch_receipt, "integration": integration, "validation": patch_validation})
    write_json(run_dir / "factory_promotion.json", promotion)
    write_json(run_dir / "safe_integrator_apply.json", safe_apply)
    write_json(run_dir / "auto_merge_gate.json", auto_gate or {"schema_version": "cento.ai_self_improvement_e2e.auto_merge_gate.v1", "status": "skipped", "dry_run": True, "push_requested": False})
    write_json(run_dir / "spend_summary.json", spend)
    validation_summary = self_e2e_validation_summary(
        run_dir,
        source=source,
        patch_receipt=patch_receipt,
        integration=integration,
        patch_validation=patch_validation,
        promotion=promotion,
        safe_apply=safe_apply,
        auto_gate=auto_gate,
        status=status,
    )
    write_json(run_dir / "validation_summary.json", validation_summary)
    manifest["status"] = status
    manifest["updated_at"] = now_iso()
    manifest["patch_swarm_run_dir"] = rel(patch_run_dir)
    manifest["factory_run_dir"] = rel(factory_run_dir) if promotion else ""
    manifest["latest_dir"] = rel(self_e2e_latest_dir())
    write_json(run_dir / "e2e_manifest.json", manifest)
    payload = {
        "status": status,
        "run_id": run_dir.name,
        "run_dir": rel(run_dir),
        "latest_dir": rel(self_e2e_latest_dir()),
        "patch_swarm_run_dir": rel(patch_run_dir),
        "factory_run_dir": rel(factory_run_dir) if promotion else "",
        "candidate_count": patch_receipt.get("candidate_count", 0),
        "selected_count": integration.get("selected_count", 0),
        "validation": validation_summary.get("status"),
        "spend_summary": rel(run_dir / "spend_summary.json"),
        "auto_merge_gate": rel(run_dir / "auto_merge_gate.json"),
        "handoff": rel(run_dir / "handoff.md"),
    }
    write_self_e2e_handoff(run_dir, payload)
    mirror_self_e2e_latest(run_dir)
    print(json.dumps(payload, indent=2) if args.json else f"{status} {rel(run_dir)}")
    return 0 if status in {"ready_for_apply", "applied", "auto_merge_blocked_by_environment"} else 1


def command_self_improve_validate(args: argparse.Namespace) -> int:
    run_dir = resolve_self_run_dir(args.run_dir)
    gates = self_improve_validation(run_dir)
    if run_dir.name == (read_json(self_latest_dir() / "nightly_cycle_manifest.json").get("cycle_id") or ""):
        write_self_json(run_dir, "validation_gates.json", gates)
    else:
        write_json(run_dir / "validation_gates.json", gates)
    payload = {"run_dir": rel(run_dir), **gates}
    print(json.dumps(payload, indent=2) if args.json else f"{gates['status']} {rel(run_dir)}")
    return 0 if gates.get("status") == "passed" else 1


def self_improve_status_payload(run_dir: Path | None, *, crontab_file: str = "") -> dict[str, Any]:
    crontab_text = read_crontab(crontab_file)
    cron_installed = SELF_CRON_BEGIN in crontab_text and SELF_CRON_END in crontab_text
    payload: dict[str, Any] = {
        "run_dir": rel(run_dir) if run_dir else "",
        "latest_dir": rel(self_latest_dir()),
        "cron_installed": cron_installed,
        "cron_block": self_cron_block("02:30") if cron_installed else "",
    }
    if run_dir:
        manifest = read_json(run_dir / "nightly_cycle_manifest.json")
        gates = read_json(run_dir / "validation_gates.json")
        metrics = read_json(run_dir / "loop_metrics.json")
        recommendation = read_json(run_dir / "promotion_recommendation.json")
        payload.update(
            {
                "cycle_id": manifest.get("cycle_id", run_dir.name),
                "status": "completed" if gates.get("status") == "passed" else ("blocked" if gates else "unknown"),
                "validation": gates.get("status", "unknown"),
                "degraded_pass_count": metrics.get("degraded_pass_count", 0),
                "promotion_recommendation": recommendation.get("recommendation", "unknown"),
                "next_cycle_request": rel(run_dir / "next_cycle_request.json"),
            }
        )
    else:
        payload.update({"status": "unknown", "validation": "unknown", "promotion_recommendation": "unknown"})
    return payload


def command_self_improve_status(args: argparse.Namespace) -> int:
    run_dir = resolve_self_run_dir(args.run_dir) if args.run_dir or self_improve_latest_run_dir() else None
    payload = self_improve_status_payload(run_dir, crontab_file=args.crontab_file)
    print(json.dumps(payload, indent=2) if args.json else f"{payload['status']} {payload['validation']} {payload['run_dir']}")
    return 0


def command_self_improve_install_cron(args: argparse.Namespace) -> int:
    try:
        block = self_cron_block(args.time)
    except ValueError as exc:
        print(f"parallel-delivery self-improve install-cron: {exc}", file=sys.stderr)
        return 2
    current = read_crontab(args.crontab_file)
    updated = strip_self_cron_block(current)
    if updated.strip():
        updated = updated.rstrip() + "\n"
    updated += block
    if not args.dry_run:
        write_crontab(updated, args.crontab_file)
    payload = {
        "status": "installed" if not args.dry_run else "planned",
        "time": args.time,
        "cron_block": block,
        "crontab_file": args.crontab_file,
        "dry_run": bool(args.dry_run),
    }
    print(json.dumps(payload, indent=2) if args.json else payload["status"])
    return 0


def command_self_improve_uninstall_cron(args: argparse.Namespace) -> int:
    current = read_crontab(args.crontab_file)
    updated = strip_self_cron_block(current)
    if not args.dry_run:
        write_crontab(updated, args.crontab_file)
    payload = {
        "status": "uninstalled" if not args.dry_run else "planned",
        "cron_installed_before": SELF_CRON_BEGIN in current,
        "crontab_file": args.crontab_file,
        "dry_run": bool(args.dry_run),
    }
    print(json.dumps(payload, indent=2) if args.json else payload["status"])
    return 0


def add_self_improve_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    self_cmd = sub.add_parser("self-improve", help="Run and manage the gated nightly four-pass self-improvement loop.")
    self_sub = self_cmd.add_subparsers(dest="self_command", required=True)

    run = self_sub.add_parser("run", help="Run the four-pass nightly planning loop and write gated artifacts.")
    run.add_argument("--run-dir", default="")
    run.add_argument("--sleep-seconds", type=float, default=0.0)
    run.add_argument("--poll-seconds", type=float, default=3.0)
    run.add_argument("--per-run-timeout", type=int, default=600)
    run.add_argument("--step-timeout", type=int, default=240)
    run.add_argument("--pro-timeout", type=int, default=240)
    run.add_argument("--image-timeout", type=int, default=240)
    run.add_argument("--reference-screenshot", default="")
    run.add_argument("--live-pro", action="store_true", help="Enable live Pro planning when OPENAI_API_KEY is configured.")
    run.add_argument("--plan-only", action="store_true", help="Seed child runs without waiting for full Hard ProReq execution.")
    run.add_argument("--scheduler-trigger", default="")
    run.add_argument("--cron-time", default="02:30")
    run.add_argument("--quiet", action="store_true")
    run.add_argument("--json", action="store_true")
    run.set_defaults(func=command_self_improve_run)

    e2e = self_sub.add_parser("e2e", help="Run the self-improvement autopilot through Patch Swarm, Factory, Safe Integrator, and dry-run merge gates.")
    e2e.add_argument("--run-id", default="")
    e2e.add_argument("--candidate-target", type=int, default=30)
    e2e.add_argument("--max-parallel-agents", type=int, default=3)
    e2e.add_argument("--providers", default=",".join(PATCH_SWARM_PROVIDERS))
    e2e.add_argument("--budget-cap-usd", type=float, default=1.0)
    e2e.add_argument("--max-budget-usd", type=float, default=1.0)
    e2e.add_argument("--api-sandbox-candidates", type=int, default=1)
    e2e.add_argument("--api-profile", default=PATCH_SWARM_API_PROFILE)
    e2e.add_argument("--api-config", default=str(ROOT / ".cento" / "api_workers.yaml"))
    e2e.add_argument("--fixture-only", action="store_true", help="Use deterministic Patch Swarm fixture candidates and skip live API dispatch.")
    e2e.add_argument("--apply", action="store_true", help="Apply at most --limit selected candidate(s) in the Factory integration worktree.")
    e2e.add_argument("--validate-each", action="store_true")
    e2e.add_argument("--auto-merge-gate", action="store_true", help="Run factory merge --auto-merge-main --dry-run --json without pushing.")
    e2e.add_argument("--branch", default="")
    e2e.add_argument("--worktree", default="")
    e2e.add_argument("--limit", type=int, default=1)
    e2e.add_argument("--json", action="store_true")
    e2e.set_defaults(func=command_self_improve_e2e)

    validate = self_sub.add_parser("validate", help="Validate the latest or selected nightly self-improvement run.")
    validate.add_argument("--run-dir", default="")
    validate.add_argument("--json", action="store_true")
    validate.set_defaults(func=command_self_improve_validate)

    status = self_sub.add_parser("status", help="Show latest nightly self-improvement state and cron installation status.")
    status.add_argument("--run-dir", default="")
    status.add_argument("--crontab-file", default=os.environ.get("CENTO_SELF_IMPROVE_CRONTAB_PATH", ""))
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=command_self_improve_status)

    install = self_sub.add_parser("install-cron", help="Install the nightly cron block.")
    install.add_argument("--time", default="02:30")
    install.add_argument("--crontab-file", default=os.environ.get("CENTO_SELF_IMPROVE_CRONTAB_PATH", ""))
    install.add_argument("--dry-run", action="store_true")
    install.add_argument("--json", action="store_true")
    install.set_defaults(func=command_self_improve_install_cron)

    uninstall = self_sub.add_parser("uninstall-cron", help="Remove the nightly cron block.")
    uninstall.add_argument("--crontab-file", default=os.environ.get("CENTO_SELF_IMPROVE_CRONTAB_PATH", ""))
    uninstall.add_argument("--dry-run", action="store_true")
    uninstall.add_argument("--json", action="store_true")
    uninstall.set_defaults(func=command_self_improve_uninstall_cron)


def add_train_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    train = sub.add_parser("train", help="Plan and run a dry-run parallel integration train from a Workset.")
    train_sub = train.add_subparsers(dest="train_command", required=True)

    plan = train_sub.add_parser("plan", help="Create a dry-run train manifest and sequential integration queue.")
    plan.add_argument("--workset", required=True)
    plan.add_argument("--max-parallel", type=int, default=10)
    plan.add_argument("--run-id", default="")
    plan.add_argument("--json", action="store_true")
    plan.set_defaults(func=command_train_plan)

    run = train_sub.add_parser("run", help="Simulate train workers or execute the copied Workset through the parallel workset pipeline.")
    run.add_argument("run_id")
    run_mode = run.add_mutually_exclusive_group()
    run_mode.add_argument("--simulate", action="store_true")
    run_mode.add_argument("--workset-execute", action="store_true", help="Run the copied workset through `cento workset execute` without patch apply.")
    run.add_argument("--runtime", choices=["fixture", "local-command", "api-openai"], default="fixture")
    run.add_argument("--runtime-profile", default="")
    run.add_argument("--api-profile", default="api-section-worker")
    run.add_argument("--api-config", default=str(ROOT / ".cento" / "api_workers.yaml"))
    run.add_argument("--budget-usd", type=float, default=None, help="Target API budget; required with --runtime api-openai.")
    run.add_argument("--max-budget-usd", type=float, default=None, help="Hard API budget cap; required with --runtime api-openai.")
    run.add_argument("--validation", default="smoke")
    run.add_argument("--worker-timeout", type=int, default=None)
    run.add_argument("--retry-attempts", type=int, default=None)
    run.add_argument("--fixture-case", default="valid", choices=["valid", "unowned", "protected", "delete", "lockfile", "binary"])
    run.add_argument("--allow-dirty-owned", action="store_true")
    run.add_argument("--allow-creates", action="store_true")
    run.add_argument("--json", action="store_true")
    run.set_defaults(func=command_train_run)

    integrate = train_sub.add_parser("integrate", help="Plan sequential integration in dry-run mode.")
    integrate.add_argument("run_id")
    integrate.add_argument("--dry-run", action="store_true")
    integrate.add_argument("--json", action="store_true")
    integrate.set_defaults(func=command_train_integrate)

    status = train_sub.add_parser("status", help="Show train status.")
    status.add_argument("run_id", nargs="?", default="")
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=command_train_status)

    validate = train_sub.add_parser("validate", help="Validate train artifacts.")
    validate.add_argument("run_id", nargs="?", default="")
    validate.add_argument("--json", action="store_true")
    validate.set_defaults(func=command_train_validate)

    promote = train_sub.add_parser("promote", help="Promote a completed train Workset receipt into a Factory Safe Integrator handoff.")
    promote.add_argument("run_id")
    promote.add_argument("--dry-run", action="store_true", help="Create Factory handoff and apply plan without applying patches. This is the default.")
    promote.add_argument("--apply", action="store_true", help="Apply accepted patches into a Factory integration worktree branch.")
    promote.add_argument("--validate-each", action="store_true")
    promote.add_argument("--branch", default="")
    promote.add_argument("--worktree", default="")
    promote.add_argument("--limit", type=int, default=0)
    promote.add_argument("--json", action="store_true")
    promote.set_defaults(func=command_train_promote)

    e2e = train_sub.add_parser("e2e", help="Plan, execute, validate, and promote a Workset-backed train run.")
    e2e.add_argument("--workset", required=True)
    e2e.add_argument("--max-parallel", type=int, default=10)
    e2e.add_argument("--run-id", default="")
    e2e.add_argument("--runtime", choices=["fixture", "local-command", "api-openai"], default="fixture")
    e2e.add_argument("--runtime-profile", default="")
    e2e.add_argument("--api-profile", default="api-section-worker")
    e2e.add_argument("--api-config", default=str(ROOT / ".cento" / "api_workers.yaml"))
    e2e.add_argument("--budget-usd", type=float, default=None)
    e2e.add_argument("--max-budget-usd", type=float, default=None)
    e2e.add_argument("--validation", default="smoke")
    e2e.add_argument("--worker-timeout", type=int, default=None)
    e2e.add_argument("--retry-attempts", type=int, default=None)
    e2e.add_argument("--fixture-case", default="valid", choices=["valid", "unowned", "protected", "delete", "lockfile", "binary"])
    e2e.add_argument("--allow-dirty-owned", action="store_true")
    e2e.add_argument("--allow-creates", action="store_true")
    e2e.add_argument("--dry-run", action="store_true", help="Create Factory handoff and apply plan without applying patches. This is the default.")
    e2e.add_argument("--apply", action="store_true", help="Apply accepted patches into a Factory integration worktree branch.")
    e2e.add_argument("--validate-each", action="store_true")
    e2e.add_argument("--branch", default="")
    e2e.add_argument("--worktree", default="")
    e2e.add_argument("--limit", type=int, default=0)
    e2e.add_argument("--json", action="store_true")
    e2e.set_defaults(func=command_train_e2e)


def add_patch_swarm_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    swarm = sub.add_parser("patch-swarm", help="Generate, rank, and integrate many provider-diverse patch candidates.")
    swarm_sub = swarm.add_subparsers(dest="patch_swarm_command", required=True)

    plan = swarm_sub.add_parser("plan", help="Create a Patch Swarm manifest with 10 ProReq executions and one integrator.")
    plan.add_argument("--run-id", default="")
    plan.add_argument("--objective", default=PATCH_SWARM_OBJECTIVE)
    plan.add_argument("--candidate-target", type=int, default=100)
    plan.add_argument("--max-parallel-agents", type=int, default=5)
    plan.add_argument("--providers", default=",".join(PATCH_SWARM_PROVIDERS))
    plan.add_argument("--live", action="store_true", help="Mark the plan live-capable. Fixture execution remains the default.")
    plan.add_argument("--json", action="store_true")
    plan.set_defaults(func=command_patch_swarm_plan)

    split = swarm_sub.add_parser("split", help="Create Patch Swarm split-plan, task-graph, and task contract artifacts.")
    planner_tool.add_split_args(split)
    split.set_defaults(func=command_patch_swarm_split)

    leases = swarm_sub.add_parser("leases", help="Create Patch Swarm path leases from split-plan/task-graph artifacts.")
    lease_tool.add_create_args(leases)
    leases.set_defaults(func=command_patch_swarm_leases)

    validate_leases = swarm_sub.add_parser("validate-leases", help="Validate Patch Swarm path leases without applying patches.")
    lease_tool.add_validate_args(validate_leases)
    validate_leases.set_defaults(func=command_patch_swarm_validate_leases)

    prompts = swarm_sub.add_parser("prompts", help="Generate local ChatGPT Pro prompt bundles from Patch Swarm run artifacts.")
    prompts_tool.add_common_generation_args(prompts)
    prompts.set_defaults(func=command_patch_swarm_prompts)

    worker_packets = swarm_sub.add_parser("worker-packets", help="Generate local Codex worker packets from Patch Swarm task leases.")
    worker_packets.add_argument("--run-dir", required=True, help="Run directory containing request.md, split-plan.json, task-graph.json, and path-leases.json.")
    worker_packets.add_argument("--run-id", default="")
    worker_packets.add_argument("--fixture", action="store_true", help="Write deterministic fixture inputs before generating packets.")
    worker_packets.add_argument("--count", type=int, default=None)
    worker_packets.add_argument("--fixed-timestamp", default="")
    worker_packets.add_argument("--json", action="store_true")
    worker_packets.set_defaults(func=command_patch_swarm_worker_packets)

    dispatch = swarm_sub.add_parser("dispatch", help="Plan bounded dry-run Patch Swarm worker dispatch without launching agents.")
    worker_status_tool.add_dispatch_args(dispatch)
    dispatch.set_defaults(func=command_patch_swarm_dispatch)

    worker_status = swarm_sub.add_parser("worker-status", help="Show Patch Swarm worker-pool and process visibility status.")
    worker_status_tool.add_status_args(worker_status)
    worker_status.set_defaults(func=command_patch_swarm_worker_status)

    execute = swarm_sub.add_parser("execute", help="Generate normalized candidate_patch.v1 receipts.")
    execute.add_argument("run_id", nargs="?", default="")
    execute.add_argument("--fixture", action="store_true", help="Use deterministic fixture candidates. This is the default.")
    execute.add_argument("--live", action="store_true", help="Use a live-enabled plan after budget and adapter gates pass.")
    execute.add_argument("--budget-cap-usd", "--budget-cap", dest="budget_cap_usd", type=float, default=None, help="Required live provider spend cap.")
    execute.add_argument("--max-budget-usd", type=float, default=None, help="Optional hard live cap ceiling. Defaults to the rollout ceiling.")
    execute.add_argument("--api-sandbox-candidates", type=int, default=1, help="Maximum metered api-openai patch_proposal.v1 candidates to dispatch.")
    execute.add_argument("--api-profile", default=PATCH_SWARM_API_PROFILE)
    execute.add_argument("--api-config", default=str(ROOT / ".cento" / "api_workers.yaml"))
    execute.add_argument("--json", action="store_true")
    execute.set_defaults(func=command_patch_swarm_execute)

    integrate = swarm_sub.add_parser("integrate", help="Run the dedicated serialized integration execution.")
    integrate.add_argument("run_id", nargs="?", default="")
    integrate.add_argument("--dry-run", action="store_true", help="Write Safe Integrator handoff without applying patches. This is the default.")
    integrate.add_argument("--apply", action="store_true", help="Apply selected candidates in a Factory/Safe Integrator worktree.")
    integrate.add_argument("--factory-run", default="", help="Factory run directory. Defaults to workspace/runs/factory/patch-swarm-RUN.")
    integrate.add_argument("--validate-each", action="store_true")
    integrate.add_argument("--branch", default="")
    integrate.add_argument("--worktree", default="")
    integrate.add_argument("--limit", type=int, default=0)
    integrate.add_argument("--json", action="store_true")
    integrate.set_defaults(func=command_patch_swarm_integrate)

    validate = swarm_sub.add_parser("validate", help="Validate Patch Swarm artifacts, candidate counts, providers, and integration handoff.")
    validate.add_argument("run_id", nargs="?", default="")
    validate.add_argument("--json", action="store_true")
    validate.set_defaults(func=command_patch_swarm_validate)

    status = swarm_sub.add_parser("status", help="Show latest or selected Patch Swarm status.")
    status.add_argument("run_id", nargs="?", default="")
    status.add_argument("--run-dir", default="", help="Read console status from an explicit Patch Swarm run directory.")
    status.add_argument("--output-dir", default="", help="Write console export files here. Defaults to --run-dir.")
    status.add_argument("--write-html", action="store_true", help="Write start-here.html next to console-data.json.")
    status.add_argument("--strict-links", action="store_true", help="Fail if generated console links are missing or escape the run directory.")
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=command_patch_swarm_status)

    e2e = swarm_sub.add_parser("e2e", help="Plan, generate 100+ candidates, integrate winners, and validate.")
    e2e.add_argument("--run-id", default="")
    e2e.add_argument("--run-root", default=str(validation_e2e_tool.DEFAULT_RUN_ROOT), help="Fixture E2E run root.")
    e2e.add_argument("--output-dir", default="", help="Exact fixture run directory to write. Overrides --run-root when provided.")
    e2e.add_argument("--objective", default=PATCH_SWARM_OBJECTIVE)
    e2e.add_argument("--candidate-target", type=int, default=100)
    e2e.add_argument("--max-parallel-agents", type=int, default=5)
    e2e.add_argument("--providers", default=",".join(PATCH_SWARM_PROVIDERS))
    e2e.add_argument("--fixture", action="store_true", help="Use deterministic fixture candidates. This is the default.")
    e2e.add_argument("--live", action="store_true", help="Use a live-enabled plan after budget and adapter gates pass.")
    e2e.add_argument("--budget-cap-usd", "--budget-cap", dest="budget_cap_usd", type=float, default=None)
    e2e.add_argument("--max-budget-usd", type=float, default=None)
    e2e.add_argument("--api-sandbox-candidates", type=int, default=1)
    e2e.add_argument("--api-profile", default=PATCH_SWARM_API_PROFILE)
    e2e.add_argument("--api-config", default=str(ROOT / ".cento" / "api_workers.yaml"))
    e2e.add_argument("--apply", action="store_true", help="Apply selected candidates in a Factory/Safe Integrator worktree.")
    e2e.add_argument("--factory-run", default="")
    e2e.add_argument("--validate-each", action="store_true")
    e2e.add_argument("--branch", default="")
    e2e.add_argument("--worktree", default="")
    e2e.add_argument("--limit", type=int, default=0)
    e2e.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=True, help="Write dry-run integration receipts without applying patches. This is the fixture default.")
    e2e.add_argument("--fixed-timestamp", default="", help="Use a deterministic timestamp for fixture E2E artifacts.")
    e2e.add_argument("--include-unsafe-fixture", action=argparse.BooleanOptionalAction, default=True, help="Include an unsafe out-of-lease bundle and prove it is rejected.")
    e2e.add_argument("--json", action="store_true")
    e2e.set_defaults(func=command_patch_swarm_e2e)


def add_patch_bundles_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    bundles = sub.add_parser("patch-bundles", help="Collect and validate local Patch Swarm patch bundles.")
    bundle_sub = bundles.add_subparsers(dest="patch_bundle_command", required=True)

    validate = bundle_sub.add_parser("validate", help="Validate one local Patch Swarm bundle without applying it.")
    validate.add_argument("--bundle", required=True)
    validate.add_argument("--lease-manifest", required=True)
    validate.add_argument("--out", required=True)
    validate.add_argument("--run-id", default="")
    validate.add_argument("--base-commit", default="")
    validate.add_argument("--json", action="store_true")
    validate.set_defaults(func=command_patch_bundles_validate)

    collect = bundle_sub.add_parser("collect", help="Collect and validate a directory of local Patch Swarm bundles.")
    collect.add_argument("--bundles-dir", required=True)
    collect.add_argument("--lease-manifest", required=True)
    collect.add_argument("--out", required=True)
    collect.add_argument("--run-id", required=True)
    collect.add_argument("--base-commit", default="")
    collect.add_argument("--json", action="store_true")
    collect.set_defaults(func=command_patch_bundles_collect)


def add_release_candidate_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    release = sub.add_parser("release-candidate", help="Create safe apply receipts and release-candidate evidence from accepted integration receipts.")
    release_sub = release.add_subparsers(dest="release_candidate_command", required=True)

    create = release_sub.add_parser("create", help="Dry-run or apply accepted patch bundles in an isolated target and write release-candidate evidence.")
    release_candidate_tool.add_create_args(create)
    create.set_defaults(func=command_release_candidate_create)


def add_taskstream_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    taskstream = sub.add_parser("taskstream", help="Emit Patch Swarm task handoff manifests for cento agent-work.")
    taskstream_sub = taskstream.add_subparsers(dest="taskstream_command", required=True)

    emit = taskstream_sub.add_parser("emit", help="Generate local story/validation manifests from a Patch Swarm split plan.")
    emit.add_argument("--split-plan", required=True)
    emit.add_argument("--out", required=True)
    emit.add_argument("--transport", choices=["auto", "mcp", "agent-work", "manifest-only"], default="manifest-only")
    emit.add_argument("--run-preflight", action=argparse.BooleanOptionalAction, default=True)
    emit.add_argument("--default-route", choices=["agent-work", "manifest-only"], default="agent-work")
    emit.add_argument("--json", action="store_true")
    emit.set_defaults(func=command_taskstream_emit)

    preflight = taskstream_sub.add_parser("preflight", help="Validate generated work packages and run safe agent-work preflight.")
    preflight.add_argument("--manifest-dir", required=True)
    preflight.add_argument("--out", required=True)
    preflight.add_argument("--json", action="store_true")
    preflight.set_defaults(func=command_taskstream_preflight)

    apply_parser = taskstream_sub.add_parser("apply", help="Submit generated work packages through approved Taskstream surfaces.")
    apply_parser.add_argument("--manifest-dir", required=True)
    apply_parser.add_argument("--out", required=True)
    apply_parser.add_argument("--transport", choices=["auto", "mcp", "agent-work"], default="auto")
    apply_parser.add_argument("--apply", action="store_true", help="Required for live task creation.")
    apply_parser.add_argument("--json", action="store_true")
    apply_parser.set_defaults(func=command_taskstream_apply)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Coordinate ProReq, Workset, integration, validation, and demo for parallel AI delivery.")
    sub = parser.add_subparsers(dest="command", required=True)

    plan = sub.add_parser("plan", help="Write the VP-level implementation manifest and demo workset.")
    plan.add_argument("--run-dir", default="")
    plan.add_argument("--json", action="store_true")
    plan.set_defaults(func=command_plan)

    execute = sub.add_parser("execute", help="Run Hard ProReq passes, compose manifests, run demo, and validate.")
    execute.add_argument("--run-dir", default="")
    execute.add_argument("--only", default="", help="Comma-separated workstream ids to run.")
    execute.add_argument("--max-passes", type=int, default=0, help="Limit passes for smoke testing.")
    execute.add_argument("--sleep-seconds", type=float, default=1.0)
    execute.add_argument("--poll-seconds", type=float, default=3.0)
    execute.add_argument("--per-run-timeout", type=int, default=600)
    execute.add_argument("--step-timeout", type=int, default=240)
    execute.add_argument("--pro-timeout", type=int, default=240)
    execute.add_argument("--image-timeout", type=int, default=240)
    execute.add_argument("--reference-screenshot", default="")
    execute.add_argument("--live-pro", action="store_true", help="Enable live Pro dispatch when OPENAI_API_KEY is configured.")
    execute.add_argument("--skip-demo", action="store_true")
    execute.add_argument("--json", action="store_true")
    execute.set_defaults(func=command_execute)

    demo = sub.add_parser("demo", help="Create and optionally execute the 10-lane fixture demo.")
    demo.add_argument("--run-dir", default="")
    demo.add_argument("--plan-only", action="store_true")
    demo.add_argument("--json", action="store_true")
    demo.set_defaults(func=command_demo)

    validate = sub.add_parser("validate", help="Validate a parallel delivery run.")
    validate.add_argument("--run-dir", default="")
    validate.add_argument("--json", action="store_true")
    validate.set_defaults(func=command_validate)

    status = sub.add_parser("status", help="Summarize the latest or selected run.")
    status.add_argument("--run-dir", default="")
    status.add_argument("--run", default="", help="Run id under --run-root.")
    status.add_argument("--run-root", default=str(RUNS_ROOT), help="Run root for --run lookup.")
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=command_status)
    add_train_parser(sub)
    add_patch_bundles_parser(sub)
    add_release_candidate_parser(sub)
    add_taskstream_parser(sub)
    add_patch_swarm_parser(sub)
    add_self_improve_parser(sub)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
