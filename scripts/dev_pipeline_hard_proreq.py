#!/usr/bin/env python3
"""Generate hard-proreq pipeline artifacts for Dev Pipeline Studio runs."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import spend_ledger


ROOT = Path(__file__).resolve().parents[1]
PIPELINE_ROOT = Path(os.environ.get("CENTO_DEV_PIPELINE_STUDIO_ROOT", ROOT / "workspace" / "runs" / "dev-pipeline-studio" / "docs-pages" / "latest"))
RESPONSES_URL = "https://api.openai.com/v1/responses"
IMAGE_EDITS_URL = "https://api.openai.com/v1/images/edits"
MODELS_URL = "https://api.openai.com/v1/models"
STORY_COUNT = int(os.environ.get("CENTO_HARD_PROREQ_STORY_COUNT", "10"))
INTEGRATION_MODEL_CEILING = os.environ.get("CENTO_PIPELINE_INTEGRATION_MODEL_CEILING", "gpt-4.1-mini")
BUDGET_TARGET_USD = float(os.environ.get("CENTO_PIPELINE_DELIVERY_BUDGET_USD", "10.00"))
BUDGET_MAX_USD = float(os.environ.get("CENTO_PIPELINE_DELIVERY_MAX_BUDGET_USD", "20.00"))


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
    if not isinstance(payload, dict):
        return {}
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def run_payload() -> dict[str, Any]:
    return read_json(PIPELINE_ROOT / "execution" / "execution_run.json")


def run_id() -> str:
    payload = run_payload()
    return str(payload.get("run_id") or "manual-hard-proreq")


def artifact_dirs() -> tuple[Path, Path]:
    current = PIPELINE_ROOT / "execution" / "hard-proreq" / run_id()
    latest = PIPELINE_ROOT / "execution" / "hard-proreq" / "latest"
    current.mkdir(parents=True, exist_ok=True)
    latest.mkdir(parents=True, exist_ok=True)
    return current, latest


def hard_proreq_spend_ledgers() -> list[Path]:
    current, _latest = artifact_dirs()
    paths = [current / "spend-ledger.jsonl"]
    walk_run_dir = os.environ.get("CENTO_WALK_AUTOPILOT_RUN_DIR", "").strip()
    if walk_run_dir:
        paths.append(Path(walk_run_dir) / "spend-ledger.jsonl")
    return paths


def append_spend(record: dict[str, Any]) -> None:
    spend_ledger.append_records(hard_proreq_spend_ledgers(), record)


def append_api_spend(
    *,
    lane: str,
    category: str,
    model: str,
    status: str,
    usage: dict[str, Any] | None = None,
    response_id: str = "",
    response: dict[str, Any] | None = None,
    artifact: str = "",
    note: str = "",
    cost_accuracy: str = "",
) -> None:
    append_spend(
        spend_ledger.build_api_record(
            run_id=run_id(),
            lane=lane,
            category=category,
            model=model,
            status=status,
            usage=usage or {},
            response_id=response_id,
            response=response,
            artifact=artifact,
            note=note,
            cost_accuracy=cost_accuracy,
        )
    )


def env_bool(name: str) -> bool:
    return os.environ.get(name, "").lower() in {"1", "true", "yes", "on"}


def env_float(name: str) -> float | None:
    value = os.environ.get(name, "").strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def metered_api_budget_gate() -> dict[str, Any]:
    if not env_bool("CENTO_REQUIRE_DASHBOARD_TOTAL_BUDGET"):
        return {"allowed": True, "status": "not-required"}
    dashboard_total = env_float("CENTO_OPENAI_DASHBOARD_TOTAL_SPEND_USD")
    hard_cap = env_float("CENTO_OPENAI_HARD_CAP_USD")
    if dashboard_total is None:
        return {
            "allowed": False,
            "status": "blocked",
            "reason": "CENTO_REQUIRE_DASHBOARD_TOTAL_BUDGET=1 but CENTO_OPENAI_DASHBOARD_TOTAL_SPEND_USD is not set.",
            "dashboard_total_spend_usd": None,
            "hard_cap_usd": hard_cap,
        }
    if hard_cap is None:
        return {
            "allowed": False,
            "status": "blocked",
            "reason": "CENTO_REQUIRE_DASHBOARD_TOTAL_BUDGET=1 but CENTO_OPENAI_HARD_CAP_USD is not set.",
            "dashboard_total_spend_usd": dashboard_total,
            "hard_cap_usd": None,
        }
    if dashboard_total >= hard_cap:
        return {
            "allowed": False,
            "status": "blocked",
            "reason": f"OpenAI dashboard total ${dashboard_total:.2f} is already >= hard cap ${hard_cap:.2f}.",
            "dashboard_total_spend_usd": dashboard_total,
            "hard_cap_usd": hard_cap,
        }
    return {
        "allowed": True,
        "status": "allowed",
        "dashboard_total_spend_usd": dashboard_total,
        "hard_cap_usd": hard_cap,
    }


def is_timeout_exception(exc: BaseException) -> bool:
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return True
    if isinstance(exc, urllib.error.URLError):
        return isinstance(exc.reason, (TimeoutError, socket.timeout))
    return False


def write_run_artifact(name: str, payload: dict[str, Any]) -> str:
    current, latest = artifact_dirs()
    payload = {**payload, "written_at": now_iso()}
    current_path = current / name
    latest_path = latest / name
    write_json(current_path, payload)
    write_json(latest_path, payload)
    return rel(current_path)


def write_run_artifact_path(relative_name: str, payload: dict[str, Any]) -> str:
    current, latest = artifact_dirs()
    payload = {**payload, "written_at": now_iso()}
    current_path = current / relative_name
    latest_path = latest / relative_name
    write_json(current_path, payload)
    write_json(latest_path, payload)
    return rel(current_path)


def slugify(value: str, fallback: str = "story") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return slug[:64] or fallback


def copy_run_file(name: str, source: Path) -> str:
    current, latest = artifact_dirs()
    current_path = current / name
    latest_path = latest / name
    current_path.parent.mkdir(parents=True, exist_ok=True)
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != current_path.resolve():
        shutil.copyfile(source, current_path)
    if source.resolve() != latest_path.resolve():
        shutil.copyfile(source, latest_path)
    return rel(current_path)


def write_run_bytes(name: str, payload: bytes) -> str:
    current, latest = artifact_dirs()
    current_path = current / name
    latest_path = latest / name
    current_path.parent.mkdir(parents=True, exist_ok=True)
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    current_path.write_bytes(payload)
    latest_path.write_bytes(payload)
    return rel(current_path)


def write_run_text(name: str, payload: str) -> str:
    current, latest = artifact_dirs()
    current_path = current / name
    latest_path = latest / name
    current_path.parent.mkdir(parents=True, exist_ok=True)
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    current_path.write_text(payload, encoding="utf-8")
    latest_path.write_text(payload, encoding="utf-8")
    return rel(current_path)


def operator_prompt() -> str:
    payload = run_payload()
    prompt = "\n\n".join(
        part.strip()
        for part in [
            str(payload.get("issue_subject") or ""),
            str(payload.get("prompt") or ""),
        ]
        if part and part.strip()
    )
    return prompt or "Manual hard proreq run from Dev Pipeline Studio."


def image_focus_prompt() -> str:
    return os.environ.get("CENTO_HARD_PROREQ_IMAGE_TASK", "").strip() or operator_prompt()


def reference_screenshot() -> tuple[str, Path | None]:
    screenshot_input = run_input("ui-screenshot-request")
    input_refs = screenshot_input.get("image_refs") if isinstance(screenshot_input.get("image_refs"), list) else []
    candidates = [
        os.environ.get("CENTO_HARD_PROREQ_REFERENCE_SCREENSHOT", ""),
        *[str(item) for item in input_refs if isinstance(item, str) and item.strip()],
        "workspace/runs/agent-work/dev-pipeline-studio-execution-flow/input-sequence-list-wide.png",
        "workspace/runs/agent-work/dev-pipeline-studio-execution-flow/execution-flow.png",
        "workspace/runs/agent-work/dev-pipeline-studio-execution-flow/input-sequence-list.png",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if not path.is_absolute():
            path = ROOT / candidate
        if path.exists() and path.is_file():
            return copy_run_file("existing_ui_reference.png", path), path
    return "", None


def build_integrator_image_prompt(focus: str) -> str:
    return (
        "Using the supplied Cento Dev Pipeline Studio screenshot only as the visual style reference, "
        "generate a new product UI screenshot that documents the Integrator part of the pipeline. "
        "Keep the same dark industrial UI language, orange/cyan/purple accents, dense operational layout, "
        "thin borders, compact controls, and non-marketing console feel. "
        "The screenshot should clearly show an Integrator lane where backend workstreams converge into one serialized integration step, "
        "then flow into deterministic validation and evidence handoff. "
        "Include visible labels: Integrator, Serialized integration, Backend work manifest, Integration plan, Validation gates, Evidence handoff. "
        "Make it look like an actual in-app screenshot, not a presentation slide. "
        f"Specific user request: {focus[:1200]}"
    )


def run_input(input_id: str) -> dict[str, Any]:
    payload = run_payload()
    for item in payload.get("inputs") or []:
        if isinstance(item, dict) and str(item.get("id") or "") == input_id:
            return item
    return {}


def image_lane_is_automated() -> bool:
    item = run_input("ui-screenshot-request")
    if not item:
        return True
    return str(item.get("source") or "").lower() == "auto" and str(item.get("automation") or item.get("automation_source") or "").lower() in {"openai-image", "image", "screenshot"}


def square_reference_image(reference_path: Path) -> Path | None:
    try:
        from PIL import Image
    except Exception:
        return None
    current, latest = artifact_dirs()
    current_path = current / "existing_ui_reference_square.png"
    latest_path = latest / "existing_ui_reference_square.png"
    with Image.open(reference_path) as image:
        image = image.convert("RGBA")
        image.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (1024, 1024), (9, 9, 9, 255))
        canvas.paste(image, ((1024 - image.width) // 2, (1024 - image.height) // 2))
        current_path.parent.mkdir(parents=True, exist_ok=True)
        latest_path.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(current_path, "PNG")
        canvas.save(latest_path, "PNG")
    return current_path


def image2_preflight(requests_module: Any, model: str) -> dict[str, Any]:
    if model != "gpt-image-2":
        return {"status": "not-required", "requested_model": model, "selected_model": model, "fallback_used": False}
    if os.environ.get("CENTO_HARD_PROREQ_DISABLE_GPT_IMAGE_2", "0").lower() not in {"0", "false", "no", "off"}:
        return {
            "status": "disabled",
            "requested_model": model,
            "selected_model": "gpt-image-1",
            "fallback_used": True,
            "reason": "gpt-image-2 is disabled until a capability check passes.",
        }
    try:
        response = requests_module.get(
            f"{MODELS_URL}/gpt-image-2",
            headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
            timeout=int(os.environ.get("CENTO_HARD_PROREQ_IMAGE_PREFLIGHT_TIMEOUT", "12")),
        )
    except Exception as exc:
        return {
            "status": "check-failed",
            "requested_model": model,
            "selected_model": "gpt-image-1",
            "fallback_used": True,
            "reason": f"{type(exc).__name__}: {exc}",
        }
    if getattr(response, "status_code", 0) == 200:
        return {"status": "passed", "requested_model": model, "selected_model": model, "fallback_used": False}
    reason = ""
    try:
        payload = response.json()
        reason = json.dumps(payload, sort_keys=True)[:1000]
    except Exception:
        reason = str(getattr(response, "text", ""))[:1000]
    return {
        "status": "blocked",
        "requested_model": model,
        "selected_model": "gpt-image-1",
        "fallback_used": True,
        "http_status": getattr(response, "status_code", 0),
        "reason": reason or "gpt-image-2 capability check did not pass.",
    }


def image2_org_verification_blocked(status_code: int, payload: dict[str, Any]) -> bool:
    if status_code != 403:
        return False
    text = json.dumps(payload, sort_keys=True).lower()
    return "verify" in text or "verification" in text or "organization" in text or "org" in text


def dispatch_image_generation(request: dict[str, Any], reference_path: Path | None) -> dict[str, Any]:
    def skipped(reason: str, *, code: str) -> dict[str, Any]:
        response_record = {
            "schema_version": "cento.hard_proreq.image_response.v1",
            "run_id": run_id(),
            "status": "skipped",
            "skip_code": code,
            "lane": "frontend-muted",
            "blocking": False,
            "error": reason,
            "model": str(request.get("model") or ""),
        }
        write_run_artifact("image_generation_response.json", response_record)
        return response_record

    if not reference_path:
        return skipped("No existing UI reference screenshot was available.", code="missing-reference-image")
    if not os.environ.get("OPENAI_API_KEY"):
        return skipped("OPENAI_API_KEY is not configured.", code="missing-openai-api-key")
    try:
        import requests
    except Exception as exc:
        return skipped(f"requests import failed: {exc}", code="requests-unavailable")
    budget_gate = metered_api_budget_gate()
    if not bool(budget_gate.get("allowed")):
        write_run_artifact("image_generation_budget_gate.json", budget_gate)
        append_api_spend(
            lane="image",
            category="image",
            model=str(request.get("model") or ""),
            status="skipped",
            artifact="image_generation_budget_gate.json",
            note=str(budget_gate.get("reason") or "dashboard budget gate blocked image generation"),
            cost_accuracy="budget-gated",
        )
        return skipped(str(budget_gate.get("reason") or "Dashboard budget gate blocked image generation."), code="dashboard-budget-gate")

    params = request.get("parameters") if isinstance(request.get("parameters"), dict) else {}

    def post_edit(data: dict[str, str], image_path: Path) -> tuple[int, dict[str, Any]]:
        with image_path.open("rb") as handle:
            response = requests.post(
                IMAGE_EDITS_URL,
                headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
                data=data,
                files=[("image[]", (image_path.name, handle, "image/png"))],
                timeout=int(os.environ.get("CENTO_HARD_PROREQ_IMAGE_TIMEOUT", "240")),
            )
        try:
            payload = response.json()
        except Exception:
            payload = {"raw": response.text[:4000]}
        return response.status_code, payload

    data = {
        "model": str(request.get("model") or "gpt-image-2"),
        "prompt": str(request.get("prompt") or ""),
        "size": str(params.get("size") or "1024x1536"),
        "quality": str(params.get("quality") or "low"),
        "n": str(params.get("n") or 1),
        "output_format": str(params.get("output_format") or "png"),
    }
    preflight = image2_preflight(requests, data["model"])
    data["model"] = str(preflight.get("selected_model") or data["model"])
    if data["model"] != "gpt-image-2":
        data["input_fidelity"] = str(params.get("input_fidelity") or "high")
    append_api_spend(
        lane="image",
        category="image",
        model=data["model"],
        status="started",
        artifact="image_generation_request.json",
        note=f"image edit attempt starting; preflight={preflight.get('status')}",
    )
    status_code, payload = post_edit(data, reference_path)
    append_api_spend(
        lane="image",
        category="image",
        model=data["model"],
        status="completed" if status_code < 400 else "failed",
        usage=payload.get("usage") if isinstance(payload.get("usage"), dict) else {},
        response=payload if isinstance(payload, dict) else {},
        artifact="image_generation_response.json",
        note=f"image edit attempt; preflight={preflight.get('status')}",
    )
    attempts = [
        {
            "model": data["model"],
            "http_status": status_code,
            "status": "completed" if status_code < 400 else "failed",
            "preflight": preflight,
        }
    ]
    if data["model"] == "gpt-image-2" and image2_org_verification_blocked(status_code, payload):
        fallback_data = {**data, "model": "gpt-image-1", "input_fidelity": str(params.get("input_fidelity") or "high")}
        append_api_spend(
            lane="image",
            category="image",
            model=fallback_data["model"],
            status="started",
            artifact="image_generation_request.json",
            note="image edit fallback starting after gpt-image-2 org verification block",
        )
        status_code, payload = post_edit(fallback_data, reference_path)
        data = fallback_data
        attempts.append(
            {
                "model": data["model"],
                "http_status": status_code,
                "status": "completed" if status_code < 400 else "failed",
                "fallback_reason": "gpt-image-2 returned an org verification 403",
            }
        )
        append_api_spend(
            lane="image",
            category="image",
            model=data["model"],
            status="completed" if status_code < 400 else "failed",
            usage=payload.get("usage") if isinstance(payload.get("usage"), dict) else {},
            response=payload if isinstance(payload, dict) else {},
            artifact="image_generation_response.json",
            note="image edit fallback attempt after gpt-image-2 org verification block",
        )
    if status_code >= 400:
        response_record = {
            "schema_version": "cento.hard_proreq.image_response.v1",
            "run_id": run_id(),
            "status": "failed",
            "http_status": status_code,
            "model": data.get("model"),
            "requested_model": str(request.get("model") or ""),
            "preflight": preflight,
            "attempts": attempts,
            "response": payload,
        }
        write_run_artifact("image_generation_response.json", response_record)
        return response_record

    image_b64 = ""
    data_items = payload.get("data") if isinstance(payload.get("data"), list) else []
    if data_items and isinstance(data_items[0], dict):
        image_b64 = str(data_items[0].get("b64_json") or "")
    output_rel = ""
    if image_b64:
        output_rel = write_run_bytes("generated_integrator_screenshot.png", base64.b64decode(image_b64))
    response_record = {
        "schema_version": "cento.hard_proreq.image_response.v1",
        "run_id": run_id(),
        "status": "completed" if output_rel else "failed",
        "http_status": status_code,
        "model": data["model"],
        "requested_model": str(request.get("model") or ""),
        "preflight": preflight,
        "attempts": attempts,
        "output_image": output_rel,
        "usage": payload.get("usage") if isinstance(payload.get("usage"), dict) else {},
        "created": payload.get("created"),
        "data_count": len(data_items),
        "response_without_image": {key: value for key, value in payload.items() if key != "data"},
    }
    write_run_artifact("image_generation_response.json", response_record)
    return response_record


def output_schema() -> dict[str, Any]:
    text = {"type": "string"}
    text_array = {"type": "array", "items": {"type": "string"}}
    workstream = {
        "type": "object",
        "properties": {
            "id": text,
            "title": text,
            "intent": text,
            "owned_paths": text_array,
            "read_paths": text_array,
            "depends_on": text_array,
            "validation_commands": text_array,
            "handoff_artifacts": text_array,
        },
        "required": ["id", "title", "intent", "owned_paths", "read_paths", "depends_on", "validation_commands", "handoff_artifacts"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "schema_version": {"type": "string", "enum": ["cento.hard_proreq_backend_plan.v1"]},
            "summary": text,
            "backend_workstreams": {"type": "array", "items": workstream},
            "integration_plan": text_array,
            "validation_plan": text_array,
            "parallelization_notes": text_array,
            "codex_exec_prompts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": text,
                        "prompt": text,
                        "output_schema": text,
                    },
                    "required": ["id", "prompt", "output_schema"],
                    "additionalProperties": False,
                },
            },
            "risks": text_array,
        },
        "required": ["schema_version", "summary", "backend_workstreams", "integration_plan", "validation_plan", "parallelization_notes", "codex_exec_prompts", "risks"],
        "additionalProperties": False,
    }


def bounded_command(command: list[str], timeout: int = 8, limit: int = 8000) -> dict[str, Any]:
    try:
        result = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)
    except Exception as exc:
        return {"command": command, "exit_code": 1, "stdout": "", "stderr": str(exc)}
    return {
        "command": command,
        "exit_code": result.returncode,
        "stdout": (result.stdout or "")[-limit:],
        "stderr": (result.stderr or "")[-limit:],
    }


def search_terms(prompt: str) -> list[str]:
    candidates = re.findall(r"[A-Za-z][A-Za-z0-9_-]{3,}", prompt.lower())
    stop = {"this", "that", "with", "from", "have", "should", "would", "could", "pipeline", "project"}
    terms = ["hard-proreq", "dev-pipeline", "agent_work_app", "cento_openai_worker"]
    for item in candidates:
        if item not in stop and item not in terms:
            terms.append(item)
        if len(terms) >= 10:
            break
    return terms


def command_intake(_args: argparse.Namespace) -> int:
    payload = run_payload()
    prompt = operator_prompt()
    write_run_artifact(
        "operator_intake.json",
        {
            "schema_version": "cento.hard_proreq.operator_intake.v1",
            "run_id": run_id(),
            "issue_id": str(payload.get("issue_id") or ""),
            "issue_subject": str(payload.get("issue_subject") or ""),
            "triggered_by": str(payload.get("triggered_by") or ""),
            "operator_prompt": prompt,
            "questionnaire_answers": [],
            "source": "run_pipeline_contract" if str(payload.get("triggered_by") or "") == "pipeline-run-api" else ("taskstream_issue" if payload.get("issue_id") else "manual_rerun"),
        },
    )
    return 0


def command_context(_args: argparse.Namespace) -> int:
    prompt = operator_prompt()
    terms = search_terms(prompt)
    rg_hits: list[dict[str, Any]] = []
    for term in terms[:5]:
        result = bounded_command(["rg", "-n", "--glob", "!**/node_modules/**", term, "scripts", "templates", "docs", "data", "tests"], timeout=3, limit=3000)
        rg_hits.append({"term": term, "exit_code": result["exit_code"], "matches": result["stdout"].splitlines()[:20]})
    write_run_artifact(
        "mini_cento_context.json",
        {
            "schema_version": "cento.hard_proreq.mini_context.v1",
            "run_id": run_id(),
            "prompt_terms": terms,
            "cento_context": bounded_command(["cento", "gather-context", "--no-remote"], timeout=10, limit=7000),
            "cento_tools": bounded_command(["cento", "tools"], timeout=8, limit=7000),
            "repo_search": rg_hits,
            "summary": [
                "Use Cento-native tools before creating work.",
                "Use Taskstream/agent-work for backend work decomposition.",
                "Use OpenAI Responses strict JSON Schema for GPT pro backend planning.",
                "Keep UI screenshot generation in a separate muted frontend lane.",
            ],
        },
    )
    return 0


def write_screenshot_request(*, allow_dispatch: bool = True, disabled_reason: str = "") -> int:
    prompt = operator_prompt()
    focus = image_focus_prompt()
    reference_rel, reference_path = reference_screenshot()
    image_prompt = build_integrator_image_prompt(focus)
    image_request = {
        "schema_version": "cento.hard_proreq.image_generation_request.v1",
        "endpoint": "POST /v1/images/edits",
        "api_surface": "OpenAI Image API",
        "model": os.environ.get("CENTO_OPENAI_IMAGE_MODEL", "gpt-image-2"),
        "reference_images": [reference_rel] if reference_rel else [],
        "prompt": image_prompt,
        "parameters": {
            "size": os.environ.get("CENTO_HARD_PROREQ_IMAGE_SIZE", "1024x1536"),
            "quality": os.environ.get("CENTO_HARD_PROREQ_IMAGE_QUALITY", "low"),
            "output_format": "png",
            "input_fidelity": "high",
            "n": 1,
        },
        "target_artifact": "generated_integrator_screenshot.png",
    }
    image_request_rel = write_run_artifact("image_generation_request.json", image_request)
    image_generation_status = {
        "schema_version": "cento.hard_proreq.image_response.v1",
        "run_id": run_id(),
        "status": "skipped",
        "skip_code": "image-lane-not-automated",
        "lane": "frontend-muted",
        "blocking": False,
        "error": "The ui-screenshot-request input is not configured as source=auto automation=openai-image.",
        "model": str(image_request.get("model") or ""),
    }
    if image_lane_is_automated() and allow_dispatch:
        image_generation_status = dispatch_image_generation(image_request, reference_path)
    else:
        if image_lane_is_automated() and not allow_dispatch:
            image_generation_status = {
                **image_generation_status,
                "skip_code": "image-lane-muted-by-proreq-light",
                "error": disabled_reason or "Image API dispatch is disabled for this route.",
            }
        write_run_artifact("image_generation_response.json", image_generation_status)
    write_run_artifact(
        "ui_screenshot_request.json",
        {
            "schema_version": "cento.hard_proreq.ui_screenshot_request.v1",
            "run_id": run_id(),
            "status": "muted",
            "lane": "frontend-separate",
            "reference_screenshot": reference_rel,
            "image_generation_request": image_request_rel,
            "image_generation_status": image_generation_status,
            "request_prompt": (
                "Use the existing UI screenshot as visual context, then generate a new UI screenshot for the requested pipeline documentation. "
                "Split the screenshot output into independently validatable regions, each with visible acceptance checks. "
                "Do not assign backend architecture or data-flow decisions to this lane.\n\n"
                f"Operator request:\n{prompt}\n\nImage generation prompt:\n{image_prompt}"
            ),
            "parallel_chunks": [
                {"id": "reference-style", "validation": "Existing UI reference screenshot is attached and visible to the image request."},
                {"id": "integrator-lane", "validation": "Generated screenshot documents the serialized Integrator lane and convergence from backend workstreams."},
                {"id": "validation-and-evidence", "validation": "Generated screenshot shows Integrator output flowing into validation gates and evidence handoff."},
            ],
            "muted_reason": "Frontend screenshot generation is separate from GPT pro backend planning.",
        },
    )
    return 0


def command_screenshot(_args: argparse.Namespace) -> int:
    return write_screenshot_request(allow_dispatch=True)


def command_light_screenshot(_args: argparse.Namespace) -> int:
    return write_screenshot_request(
        allow_dispatch=False,
        disabled_reason="ProReq-light keeps frontend image generation as request-only evidence to avoid metered image API dispatch.",
    )


def command_pro_request(_args: argparse.Namespace) -> int:
    current, _latest = artifact_dirs()
    schema = output_schema()
    schema_rel = write_run_artifact(
        "pro_output_schema.json",
        {
            "schema_version": "cento.hard_proreq.schema_manifest.v1",
            "schema_name": "cento_hard_proreq_backend_plan",
            "api_surface": "OpenAI Responses API text.format json_schema strict true",
            "codex_exec_flag": "--output-schema",
            "schema": schema,
        },
    )
    context = read_json(current / "mini_cento_context.json") or read_json(PIPELINE_ROOT / "execution" / "hard-proreq" / "latest" / "mini_cento_context.json")
    screenshot = read_json(current / "ui_screenshot_request.json") or read_json(PIPELINE_ROOT / "execution" / "hard-proreq" / "latest" / "ui_screenshot_request.json")
    request = {
        "model": os.environ.get("CENTO_OPENAI_PRO_MODEL", "gpt-5.4-pro"),
        "background": True,
        "instructions": (
            "You are GPT Pro acting only as a backend planning advisor for Cento. "
            "Use the operator input, mini Cento context, and questionnaire answers to produce ideal backend work separation, "
            f"integration sequencing, and validation gates. Produce exactly {STORY_COUNT} backend story workstreams. "
            "Treat frontend screenshot work as muted and separate. "
            f"Integration must be deterministic first; if model review is needed, the model ceiling is {INTEGRATION_MODEL_CEILING}. "
            "Return only compact JSON matching the strict schema; keep each list to the essential items needed for handoff."
        ),
        "input": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": json.dumps(
                            {
                                "operator_prompt": operator_prompt(),
                                "mini_cento_context": context,
                                "muted_frontend_screenshot_request": screenshot,
                                "required_output": f"exactly {STORY_COUNT} backend story workstreams, integration plan, validation plan, parallelization notes, and Codex exec prompts",
                                "budget_policy": {"target_usd": BUDGET_TARGET_USD, "max_usd": BUDGET_MAX_USD},
                                "integration_model_policy": {"deterministic_first": True, "model_ceiling": INTEGRATION_MODEL_CEILING, "only_if_needed": True},
                            },
                            indent=2,
                            sort_keys=True,
                        ),
                    }
                ],
            }
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "cento_hard_proreq_backend_plan",
                "description": "Backend-only hard proreq plan for Cento.",
                "strict": True,
                "schema": schema,
            }
        },
        "max_output_tokens": int(os.environ.get("CENTO_HARD_PROREQ_MAX_OUTPUT_TOKENS", "16000")),
        "metadata": {"schema_manifest": schema_rel, "run_id": run_id()},
    }
    write_run_artifact("pro_backend_request.json", {"schema_version": "cento.hard_proreq.pro_request.v1", "request": request})
    return 0


def extract_output_text(response: dict[str, Any]) -> str:
    direct = response.get("output_text")
    if isinstance(direct, str):
        return direct
    chunks: list[str] = []
    for item in response.get("output") or []:
        if not isinstance(item, dict):
            continue
        for content in item.get("content") or []:
            if isinstance(content, dict) and isinstance(content.get("text"), str):
                chunks.append(content["text"])
    return "".join(chunks).strip()


def extract_json_object(text: str) -> dict[str, Any]:
    text = str(text or "").strip()
    if not text:
        return {}
    candidates = [text]
    first = text.find("{")
    last = text.rfind("}")
    if first >= 0 and last > first:
        candidates.append(text[first : last + 1])
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return {}


def fallback_workstreams(prompt: str) -> list[dict[str, Any]]:
    specs = [
        (
            "run-input-contract",
            "Run Input Contract",
            "Accept operator thoughts plus optional screenshot context through the Run Pipeline API contract.",
            ["scripts/agent_work_app.py"],
            ["python3 -m py_compile scripts/agent_work_app.py"],
        ),
        (
            "hard-proreq-story-splitter",
            "Hard Proreq Story Splitter",
            "Materialize exactly ten backend story manifests from the proreq plan.",
            ["scripts/dev_pipeline_hard_proreq.py"],
            ["python3 -m py_compile scripts/dev_pipeline_hard_proreq.py"],
        ),
        (
            "parallel-workset-runner",
            "Parallel Workset Runner",
            "Run independent patch workers through exclusive write paths and serialized integration receipts.",
            ["scripts/cento_workset.py"],
            ["python3 -m py_compile scripts/cento_workset.py"],
        ),
        (
            "structured-api-worker",
            "Structured API Worker",
            "Keep patch workers structured, repo-mutating only through materialization and receipts.",
            ["scripts/cento_openai_worker.py"],
            ["python3 -m py_compile scripts/cento_openai_worker.py"],
        ),
        (
            "budget-model-guardrails",
            "Budget And Model Guardrails",
            "Apply the $10 target / $20 cap and keep integration fallback at gpt-4.1-mini or smaller.",
            [".cento/api_workers.yaml"],
            ["python3 - <<'PY'\nimport yaml\nprint(yaml.safe_load(open('.cento/api_workers.yaml'))['openai']['budget_usd_max'])\nPY"],
        ),
        (
            "run-pipeline-ui-behavior",
            "Run Pipeline UI Behavior",
            "Expose operator thoughts and optional screenshot path in the API-backed Run Pipeline modal.",
            ["templates/agent-work-app/app.js"],
            ["node --check templates/agent-work-app/app.js"],
        ),
        (
            "run-pipeline-modal",
            "Run Pipeline Modal",
            "Keep the first screen clear for entering thoughts, optional screenshot context, and starting the run.",
            ["templates/agent-work-app/index.html"],
            ["python3 - <<'PY'\nfrom pathlib import Path\nassert 'runPipelineScreenshot' in Path('templates/agent-work-app/index.html').read_text()\nPY"],
        ),
        (
            "execution-flow-styling",
            "Execution Flow Styling",
            "Keep ten-story and parallel workset UI panels readable without clipped text or overlapping cards.",
            ["templates/agent-work-app/styles.css"],
            ["python3 - <<'PY'\nfrom pathlib import Path\nassert Path('templates/agent-work-app/styles.css').exists()\nPY"],
        ),
        (
            "delivery-tests",
            "Delivery Tests",
            "Cover optional screenshot payloads, ten story manifests, and model/budget guardrails.",
            ["tests/test_dev_pipeline_delivery.py"],
            ["python3 -m pytest tests/test_dev_pipeline_delivery.py"],
        ),
        (
            "run-contract-docs",
            "Run Contract Docs",
            "Document the UI-to-ten-stories-to-parallel-patches integration contract.",
            ["docs/dev-pipeline-run-contracts.md"],
            ["python3 - <<'PY'\nfrom pathlib import Path\nassert 'ten story' in Path('docs/dev-pipeline-run-contracts.md').read_text().lower()\nPY"],
        ),
    ]
    streams: list[dict[str, Any]] = []
    for index, (stream_id, title, intent, owned_paths, commands) in enumerate(specs[:STORY_COUNT], start=1):
        streams.append(
            {
                "id": stream_id,
                "title": title,
                "intent": f"{intent} Operator request: {prompt[:360]}",
                "owned_paths": owned_paths,
                "read_paths": ["AGENTS.md", "README.md", "scripts/**", "templates/agent-work-app/**", "tests/**", "docs/**", "data/tools.json"],
                "depends_on": [] if index <= 5 else ["run-input-contract", "hard-proreq-story-splitter"],
                "validation_commands": commands,
                "handoff_artifacts": [f"stories/{stream_id}.json", "parallel_patch_workset.json"],
            }
        )
    return streams


def normalize_workstream(item: dict[str, Any], index: int, prompt: str) -> dict[str, Any]:
    fallback = fallback_workstreams(prompt)[(index - 1) % STORY_COUNT]
    stream_id = slugify(str(item.get("id") or item.get("title") or fallback["id"]), fallback["id"])
    return {
        "id": stream_id,
        "title": str(item.get("title") or fallback["title"]),
        "intent": str(item.get("intent") or item.get("description") or fallback["intent"]),
        "owned_paths": [str(value) for value in item.get("owned_paths", fallback["owned_paths"]) if isinstance(value, str) and value.strip()] or fallback["owned_paths"],
        "read_paths": [str(value) for value in item.get("read_paths", fallback["read_paths"]) if isinstance(value, str) and value.strip()] or fallback["read_paths"],
        "depends_on": [str(value) for value in item.get("depends_on", []) if isinstance(value, str) and value.strip()],
        "validation_commands": [str(value) for value in item.get("validation_commands", fallback["validation_commands"]) if isinstance(value, str) and value.strip()] or fallback["validation_commands"],
        "handoff_artifacts": [str(value) for value in item.get("handoff_artifacts", fallback["handoff_artifacts"]) if isinstance(value, str) and value.strip()] or fallback["handoff_artifacts"],
    }


def normalize_backend_plan(plan: dict[str, Any], prompt: str, risks: list[str] | None = None) -> dict[str, Any]:
    raw_streams = plan.get("backend_workstreams") if isinstance(plan.get("backend_workstreams"), list) else []
    streams = [
        normalize_workstream(item, index, prompt)
        for index, item in enumerate(raw_streams, start=1)
        if isinstance(item, dict)
    ][:STORY_COUNT]
    fallback_streams = fallback_workstreams(prompt)
    existing_ids = {stream["id"] for stream in streams}
    for item in fallback_streams:
        if len(streams) >= STORY_COUNT:
            break
        if item["id"] in existing_ids:
            continue
        streams.append(item)
        existing_ids.add(item["id"])
    integration_plan = [str(item) for item in plan.get("integration_plan", []) if isinstance(item, str) and item.strip()]
    validation_plan = [str(item) for item in plan.get("validation_plan", []) if isinstance(item, str) and item.strip()]
    parallel_notes = [str(item) for item in plan.get("parallelization_notes", []) if isinstance(item, str) and item.strip()]
    exec_prompts = [item for item in plan.get("codex_exec_prompts", []) if isinstance(item, dict)]
    if not integration_plan:
        integration_plan = [
            "Generate ten story manifests and a cento.workset.v1 parallel patch handoff before dispatch.",
            "Run patch workers in parallel only where write_paths are exclusive.",
            "Apply patch bundles through one manifest-driven sequential integrator with rollback receipts.",
            f"Use deterministic integration first; if model review is required, cap it at {INTEGRATION_MODEL_CEILING}.",
        ]
    if not validation_plan:
        validation_plan = [
            "Validate every story manifest as JSON.",
            "Run workset check before dispatch.",
            "Run py_compile, node --check, focused pytest, and UI screenshot verification.",
        ]
    if not parallel_notes:
        parallel_notes = [
            f"{len(streams)} story lanes are ready for bounded parallel patch generation.",
            "No worker may share write_paths with another worker.",
            "Integration stays serialized and receipt-backed.",
        ]
    if not exec_prompts:
        exec_prompts = [
            {
                "id": stream["id"],
                "prompt": f"Implement story {stream['title']} using only owned_paths={stream['owned_paths']}. Preserve unrelated dirty work.",
                "output_schema": "patch_proposal.v1",
            }
            for stream in streams
        ]
    return {
        "schema_version": "cento.hard_proreq_backend_plan.v1",
        "summary": str(plan.get("summary") or f"Ten-story manifest-driven backend plan for: {prompt[:240]}"),
        "backend_workstreams": streams,
        "integration_plan": integration_plan,
        "validation_plan": validation_plan,
        "parallelization_notes": parallel_notes,
        "codex_exec_prompts": exec_prompts[:STORY_COUNT],
        "risks": [str(item) for item in (risks if risks is not None else plan.get("risks", [])) if isinstance(item, str) and item.strip()],
    }


def command_pro_plan(_args: argparse.Namespace) -> int:
    current, latest = artifact_dirs()
    request_payload = read_json(current / "pro_backend_request.json") or read_json(latest / "pro_backend_request.json")
    request = request_payload.get("request") if isinstance(request_payload.get("request"), dict) else {}
    dispatch_status = "not_requested"
    dispatch_error = ""
    dispatch_skip_code = ""
    if os.environ.get("CENTO_HARD_PROREQ_DISPATCH_PRO", "").lower() in {"1", "true", "yes"} and os.environ.get("OPENAI_API_KEY") and request:
        budget_gate = metered_api_budget_gate()
        if not bool(budget_gate.get("allowed")):
            dispatch_status = "skipped"
            dispatch_skip_code = "dashboard-budget-gate"
            dispatch_error = str(budget_gate.get("reason") or "dashboard budget gate blocked Pro dispatch")
            write_run_artifact("pro_backend_budget_gate.json", budget_gate)
            append_api_spend(
                lane="pro",
                category="pro",
                model=str(request.get("model") or ""),
                status="skipped",
                artifact="pro_backend_budget_gate.json",
                note=dispatch_error,
                cost_accuracy="budget-gated",
            )
        else:
            try:
                request = {**request, "background": False}
                body = json.dumps(request).encode("utf-8")
                http = urllib.request.Request(RESPONSES_URL, data=body, method="POST", headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}", "Content-Type": "application/json"})
                timeout_seconds = int(os.environ.get("CENTO_HARD_PROREQ_PRO_TIMEOUT", "300"))
                append_api_spend(
                    lane="pro",
                    category="pro",
                    model=str(request.get("model") or ""),
                    status="started",
                    artifact="pro_backend_request.json",
                    note=f"Responses API Pro call starting; timeout_seconds={timeout_seconds}",
                )
                with urllib.request.urlopen(http, timeout=timeout_seconds) as response:
                    response_payload = json.loads(response.read().decode("utf-8"))
                dispatch_status = str(response_payload.get("status") or "unknown")
                write_run_artifact("pro_backend_response.json", {"schema_version": "cento.hard_proreq.pro_response.v1", "response": response_payload})
                append_api_spend(
                    lane="pro",
                    category="pro",
                    model=str(request.get("model") or ""),
                    status=dispatch_status,
                    usage=response_payload.get("usage") if isinstance(response_payload.get("usage"), dict) else {},
                    response=response_payload,
                    artifact="pro_backend_response.json",
                    note="Responses API Pro call completed",
                )
                output_text = extract_output_text(response_payload)
                if output_text:
                    try:
                        plan = json.loads(output_text)
                    except json.JSONDecodeError:
                        plan = {}
                    if isinstance(plan, dict) and plan.get("schema_version") == "cento.hard_proreq_backend_plan.v1":
                        write_run_artifact("pro_backend_plan.json", normalize_backend_plan(plan, operator_prompt()))
                        return 0
                dispatch_error = f"GPT pro response did not include schema JSON; status={dispatch_status}"
            except Exception as exc:
                if is_timeout_exception(exc):
                    dispatch_status = "timeout"
                    timeout_seconds = int(os.environ.get("CENTO_HARD_PROREQ_PRO_TIMEOUT", "300"))
                    dispatch_error = f"Pro Responses API call timed out after {timeout_seconds}s: {type(exc).__name__}: {exc}"
                    timeout_record = {
                        "schema_version": "cento.hard_proreq.pro_timeout.v1",
                        "run_id": run_id(),
                        "status": dispatch_status,
                        "model": str(request.get("model") or ""),
                        "timeout_seconds": timeout_seconds,
                        "error": dispatch_error,
                        "request_present": bool(request),
                    }
                    write_run_artifact("pro_backend_timeout.json", timeout_record)
                    write_run_artifact("pro_backend_response.json", {**timeout_record, "schema_version": "cento.hard_proreq.pro_response.v1"})
                    append_api_spend(
                        lane="pro",
                        category="pro",
                        model=str(request.get("model") or ""),
                        status="timeout",
                        artifact="pro_backend_timeout.json",
                        note=dispatch_error,
                        cost_accuracy="unknown-timeout",
                    )
                else:
                    dispatch_status = "failed"
                    dispatch_error = f"{type(exc).__name__}: {exc}"
                    write_run_artifact(
                        "pro_backend_error.json",
                        {
                            "schema_version": "cento.hard_proreq.pro_error.v1",
                            "run_id": run_id(),
                            "status": dispatch_status,
                            "error": dispatch_error,
                        },
                    )
                    append_api_spend(
                        lane="pro",
                        category="pro",
                        model=str(request.get("model") or ""),
                        status="failed",
                        artifact="pro_backend_error.json",
                        note=dispatch_error,
                        cost_accuracy="unknown-failed-call",
                    )

    prompt = operator_prompt()
    fallback_summary = "GPT pro request is schema-ready; backend work uses deterministic fallback until CENTO_HARD_PROREQ_DISPATCH_PRO=1 is enabled."
    fallback_risks = ["Pro API dispatch is gated unless CENTO_HARD_PROREQ_DISPATCH_PRO=1 and OPENAI_API_KEY are configured."]
    if dispatch_error:
        fallback_summary = f"GPT pro dispatch was attempted but did not return schema JSON ({dispatch_error}); backend work uses deterministic fallback."
        fallback_risks = [dispatch_error]
    skip_code = "dispatch-disabled"
    if not request:
        skip_code = "missing-request"
    elif not os.environ.get("OPENAI_API_KEY"):
        skip_code = "missing-openai-api-key"
    elif os.environ.get("CENTO_HARD_PROREQ_DISPATCH_PRO", "").lower() not in {"1", "true", "yes"}:
        skip_code = "dispatch-disabled"
    response_status = "timeout" if dispatch_status == "timeout" else ("skipped" if dispatch_skip_code else ("failed" if dispatch_error else "skipped"))
    write_run_artifact(
        "pro_backend_response.json",
        {
            "schema_version": "cento.hard_proreq.pro_response.v1",
            "run_id": run_id(),
            "status": response_status,
            "dispatch_status": dispatch_status,
            "skip_code": dispatch_skip_code or ("" if dispatch_error else skip_code),
            "error": dispatch_error,
            "model": str(request.get("model") or ""),
            "request_present": bool(request),
        },
    )
    write_run_artifact(
        "pro_backend_error.json",
        {
            "schema_version": "cento.hard_proreq.pro_error.v1",
            "run_id": run_id(),
            "status": response_status,
            "error": dispatch_error,
            "reason": fallback_risks[0] if fallback_risks else "",
        },
    )
    write_run_artifact(
        "pro_backend_plan.json",
        normalize_backend_plan(
            {
                "summary": fallback_summary,
                "backend_workstreams": fallback_workstreams(prompt),
                "risks": fallback_risks,
            },
            prompt,
            fallback_risks,
        ),
    )
    return 0


def codex_proreq_light_prompt(
    *,
    request: dict[str, Any],
    schema_payload: dict[str, Any],
    context: dict[str, Any],
    screenshot: dict[str, Any],
    prompt: str,
) -> str:
    schema = schema_payload.get("schema") if isinstance(schema_payload.get("schema"), dict) else output_schema()
    return "\n".join(
        [
            "You're chatGPT Pro model for this Cento proreq-light run.",
            "",
            "Act like the Hard ProReq ChatGPT Pro backend planning lane, but run inside Codex Exec.",
            "Use deep planning judgment, keep frontend screenshot work separate, and produce only compact JSON matching the schema.",
            "Do not write code, do not mutate the repository, and do not call external APIs from this planning step.",
            "",
            "Required JSON schema:",
            json.dumps(schema, indent=2, sort_keys=True),
            "",
            "Operator request:",
            prompt,
            "",
            "Mini Cento context:",
            json.dumps(context, indent=2, sort_keys=True)[:18000],
            "",
            "Muted frontend screenshot request:",
            json.dumps(screenshot, indent=2, sort_keys=True)[:10000],
            "",
            "Original Pro request shape to emulate:",
            json.dumps(request, indent=2, sort_keys=True)[:18000],
            "",
            "Return exactly one JSON object with schema_version=cento.hard_proreq_backend_plan.v1.",
            f"Return exactly {STORY_COUNT} backend_workstreams unless the schema forces a fallback.",
            "Each workstream must have exclusive owned_paths, read_paths, depends_on, validation_commands, and handoff_artifacts.",
            f"Use deterministic integration first; if model review is required later, cap it at {INTEGRATION_MODEL_CEILING}.",
        ]
    ).strip() + "\n"


def command_codex_pro_plan(_args: argparse.Namespace) -> int:
    current, latest = artifact_dirs()
    if not (current / "pro_backend_request.json").exists() and not (latest / "pro_backend_request.json").exists():
        command_pro_request(argparse.Namespace())
    request_payload = read_json(current / "pro_backend_request.json") or read_json(latest / "pro_backend_request.json")
    request = request_payload.get("request") if isinstance(request_payload.get("request"), dict) else {}
    schema_payload = read_json(current / "pro_output_schema.json") or read_json(latest / "pro_output_schema.json")
    context = read_json(current / "mini_cento_context.json") or read_json(latest / "mini_cento_context.json")
    screenshot = read_json(current / "ui_screenshot_request.json") or read_json(latest / "ui_screenshot_request.json")
    raw_schema = schema_payload.get("schema") if isinstance(schema_payload.get("schema"), dict) else output_schema()
    prompt_text = codex_proreq_light_prompt(
        request=request,
        schema_payload=schema_payload,
        context=context,
        screenshot=screenshot,
        prompt=operator_prompt(),
    )
    prompt_rel = write_run_text("proreq_light_codex_prompt.md", prompt_text)
    schema_rel = write_run_artifact("proreq_light_output_schema.json", raw_schema)
    schema_path = current / "proreq_light_output_schema.json"
    codex_bin = os.environ.get("CENTO_PROREQ_LIGHT_CODEX_BIN", "").strip() or shutil.which("codex") or "codex"
    command = [codex_bin, "exec", "--sandbox", "read-only", "--output-schema", str(schema_path), "-C", str(ROOT)]
    command_rel = write_run_artifact(
        "proreq_light_codex_command.json",
        {
            "schema_version": "cento.proreq_light.codex_command.v1",
            "run_id": run_id(),
            "status": "configured",
            "prompt": prompt_rel,
            "output_schema": schema_rel,
            "command": command,
            "stdin": prompt_rel,
            "cost_policy": "no metered OpenAI API; uses Codex Exec route",
        },
    )
    skip = env_bool("CENTO_PROREQ_LIGHT_SKIP_CODEX_EXEC")
    timeout_seconds = int(os.environ.get("CENTO_PROREQ_LIGHT_CODEX_TIMEOUT", "900"))
    response_record: dict[str, Any] = {
        "schema_version": "cento.proreq_light.codex_response.v1",
        "run_id": run_id(),
        "backend": "codex-exec-proreq-light",
        "prompt": prompt_rel,
        "command": command_rel,
        "status": "skipped" if skip else "started",
        "cost_usd": 0.0,
        "cost_accuracy": "no-metered-openai-api",
    }
    plan_payload: dict[str, Any] = {}
    risks: list[str] = []
    if skip:
        risks.append("Codex Exec was skipped by CENTO_PROREQ_LIGHT_SKIP_CODEX_EXEC; deterministic fallback plan was used.")
    else:
        try:
            result = subprocess.run(
                command,
                cwd=ROOT,
                input=prompt_text,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout_seconds,
                check=False,
            )
            stdout_rel = write_run_text("proreq_light_codex_stdout.txt", result.stdout or "")
            stderr_rel = write_run_text("proreq_light_codex_stderr.txt", result.stderr or "")
            plan_payload = extract_json_object(result.stdout)
            response_record.update(
                {
                    "status": "completed" if result.returncode == 0 and plan_payload else "fallback",
                    "exit_code": result.returncode,
                    "stdout": stdout_rel,
                    "stderr": stderr_rel,
                    "parsed_json": bool(plan_payload),
                }
            )
            if result.returncode != 0:
                risks.append(f"Codex Exec exited {result.returncode}; deterministic fallback plan was used.")
            if not plan_payload:
                risks.append("Codex Exec did not return parseable schema JSON; deterministic fallback plan was used.")
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout if isinstance(exc.stdout, str) else ""
            stderr = exc.stderr if isinstance(exc.stderr, str) else ""
            stdout_rel = write_run_text("proreq_light_codex_stdout.txt", stdout)
            stderr_rel = write_run_text("proreq_light_codex_stderr.txt", stderr)
            response_record.update({"status": "timeout", "stdout": stdout_rel, "stderr": stderr_rel, "timeout_seconds": timeout_seconds})
            risks.append(f"Codex Exec timed out after {timeout_seconds}s; deterministic fallback plan was used.")
        except OSError as exc:
            response_record.update({"status": "unavailable", "error": f"{type(exc).__name__}: {exc}"})
            risks.append(f"Codex Exec was unavailable ({type(exc).__name__}: {exc}); deterministic fallback plan was used.")

    if not plan_payload:
        plan_payload = {
            "schema_version": "cento.hard_proreq_backend_plan.v1",
            "summary": f"ProReq-light Codex Exec fallback plan for: {operator_prompt()[:240]}",
            "backend_workstreams": fallback_workstreams(operator_prompt()),
            "risks": risks,
        }
    normalized = normalize_backend_plan(plan_payload, operator_prompt(), risks)
    write_run_artifact("pro_backend_response.json", response_record)
    write_run_artifact(
        "pro_backend_error.json",
        {
            "schema_version": "cento.hard_proreq.pro_error.v1",
            "run_id": run_id(),
            "status": response_record.get("status"),
            "error": "; ".join(risks),
            "reason": "Codex Exec ProReq-light fallback" if risks else "",
        },
    )
    write_run_artifact("pro_backend_plan.json", normalized)
    write_run_artifact(
        "proreq_light_codex_response.json",
        {
            **response_record,
            "plan_status": "codex" if not risks and bool(plan_payload) else "fallback",
            "risk_count": len(risks),
        },
    )
    return 0


def command_backend_work(_args: argparse.Namespace) -> int:
    current, latest = artifact_dirs()
    plan = normalize_backend_plan(read_json(current / "pro_backend_plan.json") or read_json(latest / "pro_backend_plan.json"), operator_prompt())
    schema_path = rel(latest / "pro_output_schema.json")
    commands = []
    for prompt in plan.get("codex_exec_prompts", []) if isinstance(plan.get("codex_exec_prompts"), list) else []:
        if not isinstance(prompt, dict):
            continue
        prompt_file = f"workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/latest/codex_{prompt.get('id') or 'backend'}.md"
        commands.append(
            {
                "id": str(prompt.get("id") or "backend-work"),
                "prompt_file": prompt_file,
                "command": f"codex exec --output-schema {schema_path} -C {ROOT.as_posix()} < {prompt_file}",
            }
        )
    stories: list[dict[str, Any]] = []
    tasks: list[dict[str, Any]] = []
    for index, stream in enumerate(plan.get("backend_workstreams", []) if isinstance(plan.get("backend_workstreams"), list) else [], start=1):
        if not isinstance(stream, dict):
            continue
        story_id = slugify(str(stream.get("id") or f"story-{index}"), f"story-{index}")
        run_dir = f"workspace/runs/agent-work/0/hard-proreq/{run_id()}/{story_id}"
        validation_manifest = f"{run_dir}/validation.json"
        deliverables_manifest = f"{run_dir}/deliverables.json"
        deliverables_hub = f"{run_dir}/start-here.html"
        owned_paths = [str(value) for value in stream.get("owned_paths", []) if isinstance(value, str) and value.strip()]
        expected_outputs = [
            {
                "path": path,
                "description": f"Patch output owned by {story_id}",
                "owner": "hard-proreq",
                "required": True,
            }
            for path in owned_paths
        ] or [
            {
                "path": f"workspace/runs/hard-proreq/outputs/{story_id}.json",
                "description": f"Patch output owned by {story_id}",
                "owner": "hard-proreq",
                "required": True,
            }
        ]
        story = {
            "schema_version": "1.0",
            "issue": {
                "id": 0,
                "title": str(stream.get("title") or story_id),
                "package": f"hard-proreq/{run_id()}",
            },
            "lane": {
                "owner": "hard-proreq",
                "node": "linux",
                "agent": "codex-exec",
                "role": "builder",
            },
            "paths": {
                "run_dir": run_dir,
            },
            "scope": {
                "goal": str(stream.get("intent") or stream.get("title") or story_id),
                "acceptance": [
                    "Only declared owned paths are changed.",
                    "Patch proposal is returned as structured patch_proposal.v1 JSON.",
                    "Integration is accepted through a manifest-driven sequential receipt.",
                ],
            },
            "expected_outputs": expected_outputs,
            "validation": {
                "manifest": validation_manifest,
                "mode": "no-model",
                "no_model_eligible": True,
                "risk": "medium",
                "escalation_triggers": ["missing_manifest", "failed_deterministic_command", "ambiguity"],
                "commands": [str(value) for value in stream.get("validation_commands", []) if isinstance(value, str) and value.strip()]
                or [f"python3 -m json.tool {validation_manifest}"],
            },
            "deliverables": {
                "manifest": deliverables_manifest,
                "hub": deliverables_hub,
            },
            "review_gate": {
                "required_sections": ["Delivered", "Validation", "Evidence", "Residual risk"],
                "residual_risk_required": True,
            },
            "metadata": {
                "drafted_at": now_iso(),
                "source": "hard-proreq-ten-story-split",
                "integration_model_policy": {
                    "mode": "deterministic-first",
                    "fallback": "only-if-needed",
                    "model_ceiling": INTEGRATION_MODEL_CEILING,
                },
            },
        }
        story_rel = write_run_artifact_path(f"stories/{story_id}.json", story)
        validation_rel = write_run_artifact_path(
            f"stories/{story_id}.validation.json",
            {
                "schema_version": "cento.validation_manifest.v1",
                "story": story_rel,
                "commands": story["validation"]["commands"],
                "expected_outputs": expected_outputs,
            },
        )
        stories.append(
            {
                "id": story_id,
                "title": story["issue"]["title"],
                "story_manifest": story_rel,
                "validation_manifest": validation_rel,
                "owned_paths": owned_paths,
                "depends_on": [str(value) for value in stream.get("depends_on", []) if isinstance(value, str) and value.strip()],
            }
        )
        tasks.append(
            {
                "id": story_id,
                "worker_id": f"codex-story-worker-{index}",
                "task": str(stream.get("title") or story_id)[:240],
                "description": (
                    f"Implement story {story['issue']['title']} from {story_rel}. "
                    "Use Codex Exec local patch delivery. Do not edit files outside write_paths."
                ),
                "write_paths": [item["path"] for item in expected_outputs],
                "read_paths": [str(value) for value in stream.get("read_paths", []) if isinstance(value, str) and value.strip()],
                "routes": [],
                "depends_on": [str(value) for value in stream.get("depends_on", []) if isinstance(value, str) and value.strip()],
                "runtime": "local-command",
                "runtime_profile": "codex-fast",
                "cost_usd_estimate": 0.0,
            }
        )
    story_index_rel = write_run_artifact(
        "story_index.json",
        {
            "schema_version": "cento.hard_proreq.story_index.v1",
            "run_id": run_id(),
            "story_count": len(stories),
            "stories": stories,
        },
    )
    task_ids = {str(task.get("id") or "") for task in tasks}
    for task in tasks:
        task["depends_on"] = [dep for dep in task.get("depends_on", []) if dep in task_ids]
    workset_rel = write_run_artifact(
        "parallel_patch_workset.json",
        {
            "schema_version": "cento.workset.v1",
            "id": f"hard-proreq-{slugify(run_id())}",
            "mode": "standard",
            "max_parallel": min(5, max(1, len(tasks))),
            "read_paths": ["AGENTS.md", "README.md", "scripts/**", "templates/agent-work-app/**", "tests/**", "docs/**", "data/tools.json"],
            "execution_model": "parallel",
            "integration": "sequential",
            "integration_model_policy": {
                "mode": "deterministic-first",
                "fallback": "disabled-for-proreq-light",
                "model_ceiling": "none",
                "profile": "local-codex-only",
            },
            "budget": {
                "target_usd": 0.0,
                "max_usd": 0.0,
            },
            "policies": {"allow_creates": True},
            "tasks": tasks,
        },
    )
    integration_policy_rel = write_run_artifact(
        "manifest_integration_policy.json",
        {
            "schema_version": "cento.hard_proreq.integration_policy.v1",
            "run_id": run_id(),
            "integration": "sequential",
            "apply": "automatic-clean-owned-paths",
            "model_policy": {
                "deterministic_first": True,
                "fallback": "disabled-for-proreq-light",
                "model_ceiling": "none",
                "profile": "local-codex-only",
            },
            "budget": {"target_usd": 0.0, "max_usd": 0.0},
            "notifications": "muted",
        },
    )
    write_run_artifact(
        "backend_work_manifest.json",
        {
            "schema_version": "cento.hard_proreq.backend_work_manifest.v1",
            "run_id": run_id(),
            "source_plan": rel(current / "pro_backend_plan.json"),
            "story_count": len(stories),
            "story_index": story_index_rel,
            "story_manifests": [story["story_manifest"] for story in stories],
            "parallel_patch_workset": workset_rel,
            "integration_policy": integration_policy_rel,
            "workstreams": plan.get("backend_workstreams", []),
            "cento_native_commands": [
                "cento gather-context --no-remote",
                "cento tools",
                f"cento workset check {workset_rel} --allow-creates",
                f"cento workset execute {workset_rel} --max-parallel 3 --runtime local-command --runtime-profile codex-fast --allow-creates --integrate sequential --apply --validation smoke",
                "cento proreq-light deliver --max-parallel 3 --runtime-profile codex-fast --json",
                "cento agent-work create --manifest <story.json> --title <backend workstream>",
            ],
            "codex_exec": commands,
            "taskstream_creation": "planned_after_story_manifest_review",
            "notifications": "muted",
        },
    )
    return 0


def command_integration(_args: argparse.Namespace) -> int:
    current, latest = artifact_dirs()
    plan = normalize_backend_plan(read_json(current / "pro_backend_plan.json") or read_json(latest / "pro_backend_plan.json"), operator_prompt())
    backend = read_json(current / "backend_work_manifest.json") or read_json(latest / "backend_work_manifest.json")
    write_run_artifact(
        "integration_plan.json",
        {
            "schema_version": "cento.hard_proreq.integration_plan.v1",
            "run_id": run_id(),
            "steps": plan.get("integration_plan", []),
            "story_count": len(plan.get("backend_workstreams", []) if isinstance(plan.get("backend_workstreams"), list) else []),
            "parallel_patch_workset": str(backend.get("parallel_patch_workset") or "parallel_patch_workset.json"),
            "policy": "Sequential manifest-driven integration after each backend story returns evidence. No frontend screenshot artifact can own backend mutation.",
            "apply": "automatic-clean-owned-paths",
            "model_policy": {
                "deterministic_first": True,
                "fallback": "disabled-for-proreq-light",
                "model_ceiling": "none",
                "profile": "local-codex-only",
            },
            "notifications": "muted",
        },
    )
    return 0


def command_validation(_args: argparse.Namespace) -> int:
    current, latest = artifact_dirs()
    plan = normalize_backend_plan(read_json(current / "pro_backend_plan.json") or read_json(latest / "pro_backend_plan.json"), operator_prompt())
    backend = read_json(current / "backend_work_manifest.json") or read_json(latest / "backend_work_manifest.json")
    write_run_artifact(
        "validation_plan.json",
        {
            "schema_version": "cento.hard_proreq.validation_plan.v1",
            "run_id": run_id(),
            "story_count": len(plan.get("backend_workstreams", []) if isinstance(plan.get("backend_workstreams"), list) else []),
            "commands": plan.get("validation_plan", []),
            "required_local_checks": [
                "python3 -m py_compile scripts/agent_work_app.py scripts/dev_pipeline_hard_proreq.py scripts/cento_openai_worker.py",
                "node --check templates/agent-work-app/app.js",
                "python3 -m json.tool workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/latest/story_index.json",
                f"cento workset check {backend.get('parallel_patch_workset') or 'workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/latest/parallel_patch_workset.json'} --allow-creates",
                "cento proreq-light deliver --max-parallel 3 --runtime-profile codex-fast --json",
            ],
            "visual_check": "Firefox screenshot must show Hard Proreq Project selected, optional screenshot input visible, ten-story backend handoff artifacts, and frontend lane muted.",
            "notifications": "muted",
        },
    )
    return 0


def command_evidence(_args: argparse.Namespace) -> int:
    current, latest = artifact_dirs()
    names = [
        "operator_intake.json",
        "mini_cento_context.json",
        "ui_screenshot_request.json",
        "existing_ui_reference.png",
        "existing_ui_reference_square.png",
        "image_generation_request.json",
        "image_generation_response.json",
        "generated_integrator_screenshot.png",
        "pro_output_schema.json",
        "pro_backend_request.json",
        "pro_backend_response.json",
        "pro_backend_error.json",
        "pro_backend_plan.json",
        "story_index.json",
        "parallel_patch_workset.json",
        "manifest_integration_policy.json",
        "backend_work_manifest.json",
        "integration_plan.json",
        "validation_plan.json",
    ]
    artifacts = []
    for name in names:
        path = current / name
        if not path.exists():
            path = latest / name
        artifacts.append({"name": name, "path": rel(path), "exists": path.exists(), "size_bytes": path.stat().st_size if path.exists() else 0})
    write_run_artifact(
        "hard_proreq_evidence.json",
        {
            "schema_version": "cento.hard_proreq.evidence.v1",
            "run_id": run_id(),
            "status": "completed",
            "artifacts": artifacts,
            "budget": {"target_usd": BUDGET_TARGET_USD, "max_usd": BUDGET_MAX_USD},
            "notification_policy": "muted; do not send SMS or phone notifications",
        },
    )
    return 0


def command_all(args: argparse.Namespace) -> int:
    for func in [command_intake, command_context, command_screenshot, command_pro_request, command_pro_plan, command_backend_work, command_integration, command_validation, command_evidence]:
        code = func(args)
        if code:
            return code
    return 0


def command_light_all(args: argparse.Namespace) -> int:
    for func in [command_intake, command_context, command_light_screenshot, command_pro_request, command_codex_pro_plan, command_backend_work, command_integration, command_validation, command_evidence]:
        code = func(args)
        if code:
            return code
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate hard-proreq pipeline artifacts.")
    sub = parser.add_subparsers(dest="command", required=True)
    commands = {
        "intake": command_intake,
        "context": command_context,
        "screenshot": command_screenshot,
        "light-screenshot": command_light_screenshot,
        "pro-request": command_pro_request,
        "pro-plan": command_pro_plan,
        "codex-pro-plan": command_codex_pro_plan,
        "backend-work": command_backend_work,
        "integration-plan": command_integration,
        "validation-plan": command_validation,
        "evidence": command_evidence,
        "all": command_all,
        "light-all": command_light_all,
    }
    for name, func in commands.items():
        item = sub.add_parser(name)
        item.set_defaults(func=func)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
