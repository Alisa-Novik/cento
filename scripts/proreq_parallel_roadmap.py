#!/usr/bin/env python3
"""Coordinate multiple Hard ProReq passes into the parallel delivery roadmap."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


ROOT = Path(__file__).resolve().parents[1]
PIPELINE_ROOT = ROOT / "workspace" / "runs" / "dev-pipeline-studio" / "docs-pages" / "latest"
ROADMAP_PATH = ROOT / "docs" / "parallel-ai-delivery-roadmap.md"

sys.path.insert(0, str(ROOT / "scripts"))
import agent_work_app as app  # noqa: E402


BASE_VISION = (
    "Build the next big Cento delivery system: parse requirements once into exclusive "
    "parallel workstreams, run 10 AI workers to produce structured patch/artifact outputs, "
    "then converge through 2-3 integrator/validator lanes where integration and validation "
    "are deterministic first and AI is called only when deterministic gates cannot classify "
    "a conflict, missing evidence, or ambiguity. The target is 2-3 minutes instead of 10 "
    "minutes, with only $3-5 marginal AI cost."
)


PASS_SPECS: list[dict[str, str]] = [
    {
        "id": "architecture-roadmap",
        "title": "Architecture Roadmap",
        "operator_prompt": (
            f"{BASE_VISION}\n\n"
            "Focus this ProReq pass on the E2E architecture, runtime components, worker "
            "contracts, manifest flow, budget model, latency model, rollout phases, and the "
            "minimum changes needed to make the existing Cento foundation deliver this."
        ),
        "image_task": (
            "Create a product UI screenshot prompt for an architecture roadmap view showing "
            "requirements intake, planner, 10 parallel worker lanes, 2-3 integrator/validator "
            "lanes, deterministic gates, AI fallback only-if-needed, cost, and timing receipts."
        ),
    },
    {
        "id": "integration-validation-manifests",
        "title": "Integration And Validation Manifests",
        "operator_prompt": (
            f"{BASE_VISION}\n\n"
            "Focus this ProReq pass on the manifests and policies for integration and validation: "
            "story manifests, workset manifests, integration manifests, validation manifests, "
            "receipt schemas, fallback trigger packets, quarantine behavior, and rollback evidence."
        ),
        "image_task": (
            "Create a product UI screenshot prompt for the integrator/validator control surface: "
            "patch safety lane, focused test lane, release evidence lane, quarantine queue, rollback "
            "receipt, AI reviewer call only when deterministic validation cannot decide."
        ),
    },
    {
        "id": "operator-image-and-flow",
        "title": "Operator Image And Flow",
        "operator_prompt": (
            f"{BASE_VISION}\n\n"
            "Focus this ProReq pass on the operator experience and image prompt: the Dev Pipeline "
            "or Factory screen should show the request being split, 10 workers running, 2-3 "
            "validators converging, deterministic gates passing or quarantining outputs, and a "
            "clear final roadmap/release packet."
        ),
        "image_task": (
            "Generate the strongest ChatGPT image prompt for an in-app screenshot of the full "
            "parallel delivery cockpit: dense operational UI, worker lanes, validator lanes, "
            "cost/timing counters, fallback AI review marker, and final evidence handoff."
        ),
    },
]


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


def pipeline_payload(operator_prompt: str, reference_screenshot: str) -> dict[str, Any]:
    screenshot_input: dict[str, Any] = {"id": "ui-screenshot-request", "kind": "image", "source": "auto"}
    if reference_screenshot:
        screenshot_input["image_refs"] = [reference_screenshot]
        screenshot_input["image_notes"] = "Use this as visual style context for the requested delivery cockpit image."
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


def run_payload_path(run_id: str) -> Path:
    return PIPELINE_ROOT / "execution" / "runs" / f"{run_id}.json"


def run_payload(run_id: str) -> dict[str, Any]:
    return read_json(run_payload_path(run_id)) or app.dev_pipeline_artifact_json(
        app.DEV_PIPELINE_STUDIO_ROOT,
        "execution/execution_run.json",
    )


def artifact_root(run_id: str) -> Path:
    return PIPELINE_ROOT / "execution" / "hard-proreq" / run_id


def wait_for_run(run_id: str, timeout_seconds: int, poll_seconds: float) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    latest: dict[str, Any] = {}
    while time.monotonic() < deadline:
        latest = run_payload(run_id)
        status = str(latest.get("status") or "")
        if status in {"completed", "failed", "blocked", "rejected"}:
            return latest
        time.sleep(poll_seconds)
    latest = run_payload(run_id)
    latest["observed_status"] = str(latest.get("status") or "")
    latest["status"] = "timeout"
    latest["timeout_seconds"] = timeout_seconds
    return latest


def run_workset_check(workset_path: str) -> dict[str, Any]:
    if not workset_path:
        return {"status": "missing", "command": [], "exit_code": 1, "stdout": "", "stderr": "missing workset path"}
    command = ["./scripts/cento.sh", "workset", "check", workset_path]
    result = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return {
        "status": "passed" if result.returncode == 0 else "failed",
        "command": command,
        "exit_code": result.returncode,
        "stdout": result.stdout[-4000:],
        "stderr": result.stderr[-4000:],
    }


def summarize_artifacts(run_id: str) -> dict[str, Any]:
    root = artifact_root(run_id)
    backend = read_json(root / "backend_work_manifest.json")
    pro_response = read_json(root / "pro_backend_response.json")
    image_response = read_json(root / "image_generation_response.json")
    image_request = read_json(root / "image_generation_request.json")
    integration = read_json(root / "integration_plan.json")
    validation = read_json(root / "validation_plan.json")
    evidence = read_json(root / "hard_proreq_evidence.json")
    story_index = read_json(root / "story_index.json")
    workset_path = str(backend.get("parallel_patch_workset") or "")
    image_error = ""
    response_payload = image_response.get("response")
    if isinstance(response_payload, dict):
        error_payload = response_payload.get("error")
        if isinstance(error_payload, dict):
            image_error = str(error_payload.get("message") or "")
    return {
        "artifact_root": rel(root),
        "story_count": int(backend.get("story_count") or story_index.get("story_count") or 0),
        "parallel_patch_workset": workset_path,
        "integration_policy": str(backend.get("integration_policy") or ""),
        "pro_response_status": str(pro_response.get("status") or ""),
        "pro_skip_code": str(pro_response.get("skip_code") or ""),
        "pro_model": str(pro_response.get("model") or ""),
        "image_response_status": str(image_response.get("status") or ""),
        "image_skip_code": str(image_response.get("skip_code") or ""),
        "image_error": image_error,
        "image_model": str(image_response.get("model") or image_request.get("model") or ""),
        "image_request": rel(root / "image_generation_request.json"),
        "generated_image": str(image_response.get("output_image") or ""),
        "integration_steps": [str(item) for item in integration.get("steps", []) if isinstance(item, str)],
        "validation_commands": [str(item) for item in validation.get("commands", []) if isinstance(item, str)],
        "evidence_status": str(evidence.get("status") or ""),
    }


def run_one_pass(spec: dict[str, str], args: argparse.Namespace) -> dict[str, Any]:
    env_updates = {
        "CENTO_HARD_PROREQ_IMAGE_TASK": spec["image_task"],
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
            pipeline_payload(spec["operator_prompt"], args.reference_screenshot),
            spawn=False,
        )
        run_id = str(response.get("run_id") or "")
        app.dev_pipeline_spawn_execution_e2e(
            app.DEV_PIPELINE_STUDIO_ROOT,
            app.HARD_PROREQ_PROJECT_ID,
            app.HARD_PROREQ_TEMPLATE_ID,
            run_id,
        )
        final_payload = wait_for_run(run_id, args.per_run_timeout, args.poll_seconds)
    artifacts = summarize_artifacts(run_id)
    workset_check = run_workset_check(str(artifacts.get("parallel_patch_workset") or ""))
    return {
        "id": spec["id"],
        "title": spec["title"],
        "run_id": run_id,
        "status": str(final_payload.get("status") or ""),
        "duration_seconds": int(final_payload.get("duration_seconds") or 0),
        "started_at": str(final_payload.get("started_at") or ""),
        "finished_at": str(final_payload.get("finished_at") or ""),
        "operator_prompt": spec["operator_prompt"],
        "image_task": spec["image_task"],
        "artifacts": artifacts,
        "workset_check": workset_check,
        "steps": [
            {
                "id": str(step.get("id") or ""),
                "status": str(step.get("status") or ""),
                "exit_code": step.get("exit_code"),
            }
            for step in final_payload.get("steps", [])
            if isinstance(step, dict)
        ],
    }


def roadmap_lines(runs: list[dict[str, Any]], receipt_path: Path) -> list[str]:
    completed = [run for run in runs if run.get("status") == "completed"]
    pro_statuses = sorted({str(run.get("artifacts", {}).get("pro_response_status") or "unknown") for run in runs})
    image_statuses = sorted({str(run.get("artifacts", {}).get("image_response_status") or "unknown") for run in runs})
    run_table = [
        "| Pass | Status | Stories | Workset | Pro | Image |",
        "| --- | --- | ---: | --- | --- | --- |",
    ]
    for run in runs:
        artifacts = run.get("artifacts", {}) if isinstance(run.get("artifacts"), dict) else {}
        pro = artifacts.get("pro_response_status") or "unknown"
        if artifacts.get("pro_skip_code"):
            pro = f"{pro} ({artifacts.get('pro_skip_code')})"
        image = artifacts.get("image_response_status") or "unknown"
        if artifacts.get("image_skip_code"):
            image = f"{image} ({artifacts.get('image_skip_code')})"
        elif artifacts.get("image_error"):
            image_error = str(artifacts.get("image_error") or "")
            if "must be verified" in image_error:
                image = f"{image} (organization verification required)"
            else:
                image = f"{image} ({image_error[:80]})"
        run_table.append(
            "| {title} | {status} | {stories} | `{workset}` | {pro} | {image} |".format(
                title=run.get("title"),
                status=run.get("status"),
                stories=artifacts.get("story_count") or 0,
                workset=artifacts.get("parallel_patch_workset") or "",
                pro=pro,
                image=image,
            )
        )
    return [
        "# Parallel AI Delivery Roadmap",
        "",
        f"Generated by `scripts/proreq_parallel_roadmap.py` from {len(runs)} Hard ProReq passes.",
        f"Coordination receipt: `{rel(receipt_path)}`.",
        "",
        "## Objective",
        "",
        "Build the next Cento delivery layer: one requirements pass decomposes a feature into exclusive workstreams, 10 workers produce structured patch or artifact outputs in parallel, 2-3 integrator/validator lanes converge the results, and deterministic integration decides most outcomes before any extra model review is called. The target operator experience is task completion in 2-3 minutes instead of roughly 10 minutes, with only about $3-5 marginal AI cost for fanout and fallback review.",
        "",
        "## ProReq Evidence",
        "",
        *run_table,
        "",
        f"Completed passes: {len(completed)}/{len(runs)}. Pro response states: {', '.join(pro_statuses)}. Image response states: {', '.join(image_statuses)}.",
        "",
        "## Target Architecture",
        "",
        "1. Intake turns operator notes into a strict requirements packet: goal, acceptance checks, read context, owned path candidates, risk limits, budget, and validation mode.",
        "2. Planning creates 8-12 workstreams, defaulting to 10, and rejects overlapping write paths unless the overlap is moved into an explicit serialized integrator task.",
        "3. Worker fanout runs up to 10 structured workers through `cento workset execute`; workers return patch proposals or artifacts and never mutate repo files directly.",
        "4. Integration/validation runs as 2-3 deterministic lanes: patch ownership and apply checks, focused tests/UI or artifact checks, and release evidence/rollback checks.",
        "5. AI fallback is called only for unresolved ambiguity, failed deterministic validation that needs diagnosis, or conflict review, using a compact failure packet and a cheap reviewer profile such as `api-mini-integrator`.",
        "6. Handoff writes one release packet with applied patches, rejected patches, validation receipts, cost receipt, timings, rollback plan, and residual risks.",
        "",
        "## Implementation Roadmap",
        "",
        "M1: Make ProReq output directly executable by the workset layer. The generated 10-story handoff must become a checked `cento.workset.v1` manifest with `max_parallel: 10`, per-task cost estimates, and validation commands.",
        "",
        "M2: Add the integrator/validator pool without changing the worker contract. Start with three deterministic lanes: patch safety, focused validation, and release evidence. Independent failures are quarantined without blocking unrelated accepted patches.",
        "",
        "M3: Add only-if-needed AI review. Clean runs use zero reviewer calls after planning. Conflicted fixtures produce exactly one bounded reviewer artifact, then return to deterministic patch and receipt handling.",
        "",
        "M4: Benchmark speed and cost with 1, 3, 5, and 10 workers. Track wall-clock time, queue delay, integration time, model calls, and estimated cost until medium scoped tasks land in the 2-3 minute and $3-5 marginal range.",
        "",
        "M5: Expose the flow in Dev Pipeline Studio or Factory as `Run Parallel Delivery`: live worker lanes, integrator lanes, deterministic gates, fallback review calls, cost, and evidence receipts in one execution view.",
        "",
        "## Acceptance Metrics",
        "",
        "- 10 worker lanes can run concurrently when write paths are exclusive.",
        "- 2-3 integrator/validator lanes classify clean, failed, and conflicted outputs deterministically.",
        "- Clean runs complete without AI review after initial planning.",
        "- Conflicted runs call AI only with a compact failure packet and a hard budget ceiling.",
        "- Typical end-to-end completion time is 2-3 minutes for medium scoped tasks.",
        "- Marginal fanout and fallback cost stays near $3-5, with a hard stop before budget overrun.",
        "- Every run leaves receipts for worker outputs, integration decisions, validation, rollback, cost, and final handoff.",
        "",
        "## Risks",
        "",
        "Shared-file pressure is the main design risk. The system should not hide shared file edits inside parallel workers; it should emit a serialized integrator task. Validation latency is the second risk, so the next implementation needs narrow validation selection before increasing fanout. The third risk is model drift during fallback review; fallback output remains advisory unless it is converted into the same deterministic patch and receipt contract as worker output.",
    ]


def validate_roadmap(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    required = [
        "10 workers",
        "2-3 integrator",
        "2-3 minutes",
        "$3-5",
        "deterministic",
        "AI fallback",
        "only",
        "image",
    ]
    missing = [item for item in required if item.lower() not in text.lower()]
    return {"status": "passed" if not missing else "failed", "missing": missing}


def command_run(args: argparse.Namespace) -> int:
    run_dir = ROOT / "workspace" / "runs" / "proreq-roadmap" / now_stamp()
    run_dir.mkdir(parents=True, exist_ok=True)
    runs: list[dict[str, Any]] = []
    for index, spec in enumerate(PASS_SPECS):
        print(f"starting {spec['id']}", flush=True)
        record = run_one_pass(spec, args)
        runs.append(record)
        write_json(run_dir / "coordination_receipt.partial.json", {"schema_version": "cento.proreq_roadmap_receipt.v1", "runs": runs})
        print(f"finished {spec['id']} status={record['status']} run_id={record['run_id']}", flush=True)
        if index < len(PASS_SPECS) - 1 and args.sleep_seconds > 0:
            time.sleep(args.sleep_seconds)
    receipt_path = run_dir / "coordination_receipt.json"
    ROADMAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    ROADMAP_PATH.write_text("\n".join(roadmap_lines(runs, receipt_path)) + "\n", encoding="utf-8")
    roadmap_check = validate_roadmap(ROADMAP_PATH)
    worksets_ok = all(
        isinstance(run.get("workset_check"), dict) and run["workset_check"].get("status") == "passed"
        for run in runs
    )
    receipt = {
        "schema_version": "cento.proreq_roadmap_receipt.v1",
        "written_at": now_iso(),
        "status": "completed" if all(run.get("status") == "completed" for run in runs) and worksets_ok and roadmap_check["status"] == "passed" else "failed",
        "roadmap": rel(ROADMAP_PATH),
        "roadmap_check": roadmap_check,
        "live_policy": {
            "openai_api_key_present": bool(os.environ.get("OPENAI_API_KEY")),
            "live_pro_requested": bool(args.live_pro),
            "reference_screenshot": args.reference_screenshot,
        },
        "runs": runs,
    }
    write_json(receipt_path, receipt)
    write_json(run_dir / "coordination_receipt.partial.json", receipt)
    print(json.dumps({"receipt": rel(receipt_path), "roadmap": rel(ROADMAP_PATH), "status": receipt["status"]}, indent=2), flush=True)
    return 0 if receipt["status"] == "completed" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run three Hard ProReq passes and synthesize the parallel AI delivery roadmap.")
    parser.add_argument("--sleep-seconds", type=float, default=10.0, help="Sleep between ProReq passes.")
    parser.add_argument("--poll-seconds", type=float, default=3.0, help="Polling interval while a pass is running.")
    parser.add_argument("--per-run-timeout", type=int, default=600, help="Timeout per ProReq pass in seconds.")
    parser.add_argument("--step-timeout", type=int, default=360, help="Hard ProReq subprocess timeout in seconds.")
    parser.add_argument("--pro-timeout", type=int, default=360, help="Live Pro request timeout in seconds.")
    parser.add_argument("--image-timeout", type=int, default=360, help="Live image request timeout in seconds.")
    parser.add_argument("--reference-screenshot", default="", help="Optional repo-relative or absolute screenshot path for the image lane.")
    parser.add_argument("--live-pro", action="store_true", default=True, help="Enable live Pro dispatch when OPENAI_API_KEY is present.")
    parser.add_argument("--no-live-pro", action="store_false", dest="live_pro", help="Do not set CENTO_HARD_PROREQ_DISPATCH_PRO automatically.")
    parser.set_defaults(func=command_run)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
