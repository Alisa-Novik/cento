#!/usr/bin/env python3
"""Generate sequential multipipeline ProReq artifacts for Dev Pipeline Studio runs."""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PIPELINE_ROOT = Path(os.environ.get("CENTO_DEV_PIPELINE_STUDIO_ROOT", ROOT / "workspace" / "runs" / "dev-pipeline-studio" / "docs-pages" / "latest"))
HARD_PROREQ_PROJECT_ID = "hard-proreq-project"
HARD_PROREQ_TEMPLATE_ID = "hard-proreq-task"
PASS_FOCUS = [
    (
        "scope",
        "Scope and guardrails",
        "Clarify the operator-defined multipipeline objective, default compute policy, side-effect boundaries, and success evidence.",
    ),
    (
        "architecture",
        "Pipeline architecture",
        "Turn pass 1 guidance into route contracts, data artifacts, UI states, and deterministic fallback behavior.",
    ),
    (
        "integration",
        "Integration and migration",
        "Turn pass 2 guidance into implementation worksets, integration order, rollback points, and operator-facing handoff contracts.",
    ),
    (
        "validation",
        "Validation and demo",
        "Turn pass 3 guidance into validators, demo task, residual risks, and the next high-confidence execution prompt.",
    ),
]


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
    return payload if isinstance(payload, dict) else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def run_payload() -> dict[str, Any]:
    return read_json(PIPELINE_ROOT / "execution" / "execution_run.json")


def run_id() -> str:
    return str(run_payload().get("run_id") or "manual-multipipeline")


def artifact_dirs() -> tuple[Path, Path]:
    current = PIPELINE_ROOT / "execution" / "multipipeline" / run_id()
    latest = PIPELINE_ROOT / "execution" / "multipipeline" / "latest"
    current.mkdir(parents=True, exist_ok=True)
    latest.mkdir(parents=True, exist_ok=True)
    return current, latest


def write_artifact(name: str, payload: dict[str, Any]) -> str:
    current, latest = artifact_dirs()
    payload = {**payload, "written_at": now_iso()}
    current_path = current / name
    latest_path = latest / name
    write_json(current_path, payload)
    write_json(latest_path, payload)
    return rel(current_path)


def write_text_artifact(name: str, text: str) -> str:
    current, latest = artifact_dirs()
    current_path = current / name
    latest_path = latest / name
    write_text(current_path, text)
    write_text(latest_path, text)
    return rel(current_path)


def slugify(value: str, fallback: str = "item") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:64] or fallback


def pipeline_inputs() -> list[dict[str, Any]]:
    return [item for item in run_payload().get("inputs", []) if isinstance(item, dict)]


def prompt_text() -> str:
    payload = run_payload()
    prompt = str(payload.get("prompt") or "").strip()
    if prompt:
        return prompt
    for item in pipeline_inputs():
        if str(item.get("source") or "") == "user" and str(item.get("answer") or "").strip():
            return str(item.get("answer") or "").strip()
    return "Run a four-pass ProReq chain from the operator objective."


def config_text() -> str:
    for item in pipeline_inputs():
        if str(item.get("id") or "") == "multipipeline-schedule-config":
            return str(item.get("answer") or "").strip()
    return ""


def parse_config() -> dict[str, str]:
    defaults = {
        "passes": "4",
        "child_pipeline": HARD_PROREQ_TEMPLATE_ID,
        "execution_mode": "request-artifacts",
        "ui_screenshot": "request-artifact",
        "pro_call": "request-artifact",
        "handoff_policy": "previous-guidance-required",
    }
    for line in config_text().splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = re.sub(r"[^a-z0-9_]+", "_", key.strip().lower()).strip("_")
        value = value.strip()
        if key and value:
            defaults[key] = value
    defaults["passes"] = "4"
    defaults["child_pipeline"] = HARD_PROREQ_TEMPLATE_ID
    return defaults


def optional_image_refs() -> list[str]:
    refs: list[str] = []
    image_suffixes = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
    for item in pipeline_inputs():
        if str(item.get("id") or "") == "ui-screenshot-request":
            refs.extend(
                str(value)
                for value in item.get("image_refs", [])
                if isinstance(value, str) and value.strip() and Path(value).suffix.lower() in image_suffixes
            )
    return list(dict.fromkeys(refs))


def previous_guidance(pass_index: int) -> dict[str, Any]:
    if pass_index <= 1:
        return {}
    current, _latest = artifact_dirs()
    return read_json(current / f"pass_{pass_index - 1:02d}_guidance.json")


def hard_proreq_payload(pass_index: int, pass_title: str, focus: str, carry_forward: str) -> dict[str, Any]:
    operator_prompt = (
        f"Sequential ProReq chain pass {pass_index}/4: {pass_title}.\n\n"
        f"Original operator objective:\n{prompt_text()}\n\n"
        f"Focus for this pass:\n{focus}\n\n"
        f"Carry forward from previous pass:\n{carry_forward or 'No previous pass; establish guardrails and the first next-step request.'}\n\n"
        "Return integration manifests, validation manifests, UI guidance, cost-aware AI usage guidance, and a concrete next-step request for the following pass."
    )
    return {
        "schema_version": "cento.pipeline_run_request.v1",
        "project_id": HARD_PROREQ_PROJECT_ID,
        "template_id": HARD_PROREQ_TEMPLATE_ID,
        "inputs": [
            {"id": "operator-thoughts", "kind": "questionnaire", "source": "user", "answer": operator_prompt},
            {"id": "generated-cento-context", "kind": "path", "source": "auto"},
            {"id": "ui-screenshot-request", "kind": "image", "source": "auto"},
            {"id": "pro-backend-schema", "kind": "details", "source": "auto"},
            {"id": "backend-work-handoff", "kind": "evidence", "source": "auto"},
        ],
    }


def command_intake(_args: argparse.Namespace) -> int:
    write_artifact(
        "operator_intake.json",
        {
            "schema_version": "cento.multipipeline.operator_intake.v1",
            "run_id": run_id(),
            "objective": prompt_text(),
            "config": parse_config(),
            "input_ids": [str(item.get("id") or "") for item in pipeline_inputs()],
            "compute_policy": "lowest-compute request artifacts by default; no live Pro, image, or worker dispatch unless explicitly enabled",
        },
    )
    return 0


def command_schedule(_args: argparse.Namespace) -> int:
    config = parse_config()
    passes = []
    for index, (pass_id, title, focus) in enumerate(PASS_FOCUS, start=1):
        passes.append(
            {
                "id": f"pass-{index:02d}-{pass_id}",
                "sequence": index,
                "title": title,
                "child_project_id": HARD_PROREQ_PROJECT_ID,
                "child_template_id": HARD_PROREQ_TEMPLATE_ID,
                "execution_mode": config["execution_mode"],
                "depends_on": [] if index == 1 else [f"pass-{index - 1:02d}-{PASS_FOCUS[index - 2][0]}"],
                "input_artifact": f"pass_{index:02d}_proreq_request.json",
                "guidance_artifact": f"pass_{index:02d}_guidance.json",
                "focus": focus,
            }
        )
    write_artifact(
        "multipipeline_schedule.json",
        {
            "schema_version": "cento.multipipeline.schedule.v1",
            "run_id": run_id(),
            "strategy": "sequential-proreq-request-chain",
            "passes": passes,
            "handoff_policy": config["handoff_policy"],
            "live_dispatch": False,
        },
    )
    return 0


def write_pass(pass_index: int) -> int:
    pass_id, title, focus = PASS_FOCUS[pass_index - 1]
    previous = previous_guidance(pass_index)
    carry_forward = str(previous.get("next_step_request") or previous.get("summary") or "")
    payload = hard_proreq_payload(pass_index, title, focus, carry_forward)
    request_artifact = write_artifact(
        f"pass_{pass_index:02d}_proreq_request.json",
        {
            "schema_version": "cento.multipipeline.proreq_pass_request.v1",
            "run_id": run_id(),
            "pass_id": f"pass-{pass_index:02d}-{pass_id}",
            "sequence": pass_index,
            "title": title,
            "focus": focus,
            "depends_on_guidance": f"pass_{pass_index - 1:02d}_guidance.json" if pass_index > 1 else "",
            "dispatch": "request-artifact",
            "child_pipeline_payload": payload,
        },
    )
    next_request = (
        "Promote the validation/demo guidance into a scoped implementation run."
        if pass_index == 4
        else f"Use {title.lower()} guidance to drive pass {pass_index + 1}: {PASS_FOCUS[pass_index][1]}."
    )
    guidance = {
        "schema_version": "cento.multipipeline.pass_guidance.v1",
        "run_id": run_id(),
        "pass_id": f"pass-{pass_index:02d}-{pass_id}",
        "sequence": pass_index,
        "status": "completed",
        "summary": f"{title} request artifact is ready for the next sequential ProReq pass.",
        "request_artifact": request_artifact,
        "carry_forward": [
            focus,
            "Keep Pro/image/worker dispatch request-only unless explicitly enabled.",
            "Preserve deterministic integration and validation artifacts before asking another model.",
        ],
        "integration_guidance": [
            "Treat each child ProReq output as immutable evidence for the next pass.",
            "Do not merge or dispatch implementation work until the final pass evidence is accepted.",
        ],
        "validation_guidance": [
            "Check that previous guidance is cited by the next request.",
            "Block the chain if a pass omits integration, validation, UI, Pro, or next-step guidance.",
        ],
        "next_step_request": next_request,
    }
    write_artifact(f"pass_{pass_index:02d}_guidance.json", guidance)
    return 0


def command_ui_screenshot_request(_args: argparse.Namespace) -> int:
    write_artifact(
        "ui_screenshot_request.json",
        {
            "schema_version": "cento.multipipeline.ui_screenshot_request.v1",
            "run_id": run_id(),
            "status": "request-ready",
            "mode": "request-artifact",
            "reference_images": optional_image_refs(),
            "prompt": (
                "Create a minimal Cento Dev Pipeline Studio screenshot for a four-pass sequential multipipeline execution. "
                "Show a compact horizontal pass chain, current pass progress, previous-guidance handoff, UI screenshot request, "
                "ChatGPT Pro request, deterministic validation, and evidence handoff. Keep the design sparse, stable, dark, "
                "teal/orange accented, and avoid large artifact walls or jumpy layout."
            ),
        },
    )
    return 0


def command_pro_request(_args: argparse.Namespace) -> int:
    write_artifact(
        "chatgpt_pro_request.json",
        {
            "schema_version": "cento.multipipeline.chatgpt_pro_request.v1",
            "run_id": run_id(),
            "status": "request-ready",
            "mode": "request-artifact",
            "model_role": "ChatGPT Pro planning and manifest synthesis",
            "request": {
                "objective": prompt_text(),
                "required_output": [
                    "four-pass integration manifests",
                    "four-pass validation manifests",
                    "UI screenshot guidance",
                    "cost-aware AI usage guidance",
                    "next implementation/demo task",
                    "residual risks and blockers",
                ],
                "context_artifacts": [
                    "multipipeline_schedule.json",
                    "pass_01_guidance.json",
                    "pass_02_guidance.json",
                    "pass_03_guidance.json",
                    "pass_04_guidance.json",
                    "ui_screenshot_request.json",
                ],
                "constraints": [
                    "Default to request artifacts and deterministic validation.",
                    "Only propose live Pro/image/API dispatch behind explicit enablement and budget caps.",
                    "Keep child pipeline requests compatible with cento.pipeline_run_request.v1.",
                ],
            },
        },
    )
    return 0


def command_evidence(_args: argparse.Namespace) -> int:
    current, _latest = artifact_dirs()
    guidance = [read_json(current / f"pass_{index:02d}_guidance.json") for index in range(1, 5)]
    artifacts = [
        "operator_intake.json",
        "multipipeline_schedule.json",
        *[f"pass_{index:02d}_proreq_request.json" for index in range(1, 5)],
        *[f"pass_{index:02d}_guidance.json" for index in range(1, 5)],
        "ui_screenshot_request.json",
        "chatgpt_pro_request.json",
        "chain_roadmap.md",
        "multipipeline_evidence.json",
    ]
    roadmap = [
        "# Multipipeline ProReq Chain Roadmap",
        "",
        f"Run: `{run_id()}`",
        "",
        "This capability schedules four sequential ProReq request passes. Each pass consumes the previous pass guidance and prepares the next request without live Pro, image, or worker dispatch by default.",
        "",
        "## Passes",
        "",
    ]
    for item in guidance:
        roadmap.append(f"- {item.get('pass_id', 'pass')}: {item.get('summary', 'guidance ready')} Next: {item.get('next_step_request', '')}")
    roadmap.extend(
        [
            "",
            "## Handoff",
            "",
            "- Use `chatgpt_pro_request.json` when live Pro planning is explicitly desired.",
            "- Use `ui_screenshot_request.json` when UI image guidance is explicitly desired.",
            "- Use `multipipeline_evidence.json` as the validation and demo entry point.",
        ]
    )
    write_text_artifact("chain_roadmap.md", "\n".join(roadmap))
    write_artifact(
        "multipipeline_evidence.json",
        {
            "schema_version": "cento.multipipeline.evidence.v1",
            "run_id": run_id(),
            "status": "completed",
            "pass_count": 4,
            "completed_passes": [item.get("pass_id") for item in guidance if item.get("status") == "completed"],
            "artifacts": artifacts,
            "validation": {
                "sequential_handoff": all(read_json(current / f"pass_{index:02d}_proreq_request.json") for index in range(1, 5)),
                "ui_screenshot_request": (current / "ui_screenshot_request.json").exists(),
                "chatgpt_pro_request": (current / "chatgpt_pro_request.json").exists(),
                "roadmap": (current / "chain_roadmap.md").exists(),
            },
            "residual_risks": [
                "Live Pro/image execution remains request-only until credentials, budget, and explicit operator approval are present.",
                "The generated child ProReq requests are schedule artifacts; a later dispatcher must execute them if live child runs are desired.",
            ],
        },
    )
    return 0


def command_all(args: argparse.Namespace) -> int:
    for func in [command_intake, command_schedule]:
        code = func(args)
        if code:
            return code
    for index in range(1, 5):
        code = write_pass(index)
        if code:
            return code
    for func in [command_ui_screenshot_request, command_pro_request, command_evidence]:
        code = func(args)
        if code:
            return code
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate sequential multipipeline ProReq artifacts.")
    sub = parser.add_subparsers(dest="command", required=True)
    commands = {
        "intake": command_intake,
        "schedule": command_schedule,
        "ui-screenshot-request": command_ui_screenshot_request,
        "pro-request": command_pro_request,
        "evidence": command_evidence,
        "all": command_all,
    }
    for name, func in commands.items():
        item = sub.add_parser(name)
        item.set_defaults(func=func)
    for index in range(1, 5):
        item = sub.add_parser(f"pass-{index}")
        item.set_defaults(func=lambda args, pass_index=index: write_pass(pass_index))
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
