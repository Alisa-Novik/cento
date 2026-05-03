#!/usr/bin/env python3
"""OpenAI Responses API worker for Cento worksets.

The API worker produces structured artifacts only. It never mutates repository
files; Cento's local workset materializer owns file writes and patch bundles.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / ".cento" / "api_workers.yaml"
RESPONSES_URL = "https://api.openai.com/v1/responses"

SCHEMA_API_WORKER_ARTIFACT = "cento.api_worker_artifact.v1"


class WorkerError(RuntimeError):
    """Expected worker failure."""


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
    except FileNotFoundError as exc:
        raise WorkerError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise WorkerError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise WorkerError(f"expected JSON object in {path}")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def load_api_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    if not path.is_absolute():
        path = ROOT / path
    try:
        import yaml  # type: ignore

        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError as exc:
        raise WorkerError(f"api worker config not found: {rel(path)}") from exc
    except Exception as exc:
        raise WorkerError(f"failed to load api worker config {rel(path)}: {exc}") from exc
    if not isinstance(payload, dict):
        raise WorkerError(f"{rel(path)} must contain a mapping")
    return payload


def string_schema(description: str = "") -> dict[str, Any]:
    schema = {"type": "string"}
    if description:
        schema["description"] = description
    return schema


def string_array_schema(description: str = "") -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "array", "items": {"type": "string"}}
    if description:
        schema["description"] = description
    return schema


def path_content_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "path": string_schema("Repo-relative path to materialize."),
            "content": string_schema("Complete UTF-8 file content for the path."),
        },
        "required": ["path", "content"],
        "additionalProperties": False,
    }


OUTPUT_SCHEMAS: dict[str, dict[str, Any]] = {
    "docs_section.v1": {
        "type": "object",
        "properties": {
            "schema_version": {"type": "string", "enum": ["docs_section.v1"]},
            "title": string_schema("Section title."),
            "summary": string_schema("Concise section summary."),
            "badges": string_array_schema("Status, version, or state badges."),
            "body": string_schema("Primary section body or implementation notes."),
            "acceptance_criteria": string_array_schema("Concrete acceptance criteria."),
            "owned_path_contents": {
                "type": "array",
                "items": path_content_schema(),
                "description": "Optional complete file contents for owned paths.",
            },
        },
        "required": ["schema_version", "title", "summary", "badges", "body", "acceptance_criteria", "owned_path_contents"],
        "additionalProperties": False,
    },
    "workset_plan.v1": {
        "type": "object",
        "properties": {
            "schema_version": {"type": "string", "enum": ["workset_plan.v1"]},
            "summary": string_schema("Plan summary."),
            "tasks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": string_schema(),
                        "title": string_schema(),
                        "description": string_schema(),
                        "depends_on": string_array_schema(),
                        "write_paths": string_array_schema(),
                        "runtime_profile": string_schema(),
                        "output_schema": string_schema(),
                    },
                    "required": ["id", "title", "description", "depends_on", "write_paths", "runtime_profile", "output_schema"],
                    "additionalProperties": False,
                },
            },
            "risks": string_array_schema(),
        },
        "required": ["schema_version", "summary", "tasks", "risks"],
        "additionalProperties": False,
    },
    "validation_review.v1": {
        "type": "object",
        "properties": {
            "schema_version": {"type": "string", "enum": ["validation_review.v1"]},
            "status": {"type": "string", "enum": ["passed", "failed", "review"]},
            "summary": string_schema(),
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
                        "path": string_schema(),
                        "line": {"type": "integer"},
                        "message": string_schema(),
                    },
                    "required": ["severity", "path", "line", "message"],
                    "additionalProperties": False,
                },
            },
            "evidence": string_array_schema(),
            "recommended_next_steps": string_array_schema(),
        },
        "required": ["schema_version", "status", "summary", "findings", "evidence", "recommended_next_steps"],
        "additionalProperties": False,
    },
    "patch_proposal.v1": {
        "type": "object",
        "properties": {
            "schema_version": {"type": "string", "enum": ["patch_proposal.v1"]},
            "summary": string_schema(),
            "owned_path_contents": {
                "type": "array",
                "items": path_content_schema(),
                "description": "Complete file contents for proposed owned-path changes.",
            },
            "risks": string_array_schema(),
            "validation": string_array_schema(),
        },
        "required": ["schema_version", "summary", "owned_path_contents", "risks", "validation"],
        "additionalProperties": False,
    },
}


def artifact_type_for_schema(schema_name: str) -> str:
    if schema_name.endswith(".v1"):
        schema_name = schema_name[:-3]
    return schema_name.replace("-", "_")


def api_worker_artifact_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "schema_version": {"type": "string", "enum": [SCHEMA_API_WORKER_ARTIFACT]},
            "worker_id": {"type": "string"},
            "task_id": {"type": "string"},
            "status": {"type": "string", "enum": ["completed", "failed"]},
            "artifact_type": {"type": "string"},
            "owned_paths": {"type": "array", "items": {"type": "string"}},
            "content": {"type": "object"},
            "cost_usd_estimate": {"type": "number"},
            "errors": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "schema_version",
            "worker_id",
            "task_id",
            "status",
            "artifact_type",
            "owned_paths",
            "content",
            "cost_usd_estimate",
            "errors",
        ],
        "additionalProperties": False,
    }


def type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return True


def validate_json_schema(value: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    errors: list[str] = []
    expected_type = schema.get("type")
    if isinstance(expected_type, list):
        if not any(type_matches(value, str(item)) for item in expected_type):
            errors.append(f"{path} must be one of: " + ", ".join(str(item) for item in expected_type))
            return errors
    elif isinstance(expected_type, str):
        if not type_matches(value, expected_type):
            errors.append(f"{path} must be {expected_type}")
            return errors

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path} must be one of: " + ", ".join(str(item) for item in schema["enum"]))

    if isinstance(value, dict):
        required = schema.get("required") or []
        for key in required:
            if key not in value:
                errors.append(f"{path}.{key} is required")
        properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    errors.append(f"{path}.{key} is not allowed")
        for key, child_schema in properties.items():
            if key in value and isinstance(child_schema, dict):
                errors.extend(validate_json_schema(value[key], child_schema, f"{path}.{key}"))

    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        item_schema = schema["items"]
        for index, item in enumerate(value):
            errors.extend(validate_json_schema(item, item_schema, f"{path}[{index}]"))

    return errors


def profile_config(config: dict[str, Any], name: str) -> dict[str, Any]:
    profiles = config.get("profiles")
    if not isinstance(profiles, dict):
        raise WorkerError("api worker config requires profiles mapping")
    profile = profiles.get(name)
    if not isinstance(profile, dict):
        available = ", ".join(sorted(str(item) for item in profiles)) or "<none>"
        raise WorkerError(f"api worker profile not found: {name}; available profiles: {available}")
    return profile


def resolve_env_value(value: Any) -> tuple[str, str | None]:
    text = str(value or "")
    if text.startswith("${") and text.endswith("}"):
        env_name = text[2:-1]
        return os.environ.get(env_name, ""), env_name
    return text, None


def positive_int_limit(
    cli_value: int | None,
    profile: dict[str, Any],
    openai_config: dict[str, Any],
    key: str,
    default: int,
) -> int:
    value: Any = cli_value
    if value is None:
        value = profile.get(key)
    if value is None:
        value = openai_config.get(key)
    if value is None:
        value = default
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise WorkerError(f"{key} must be an integer") from exc
    if parsed <= 0:
        raise WorkerError(f"{key} must be greater than zero")
    return parsed


def build_openai_request(
    task_request: dict[str, Any],
    model: str,
    output_schema_name: str,
    *,
    max_output_tokens: int,
) -> dict[str, Any]:
    schema = OUTPUT_SCHEMAS.get(output_schema_name)
    if schema is None:
        raise WorkerError(f"unknown output schema: {output_schema_name}")
    payload = {
        "model": model,
        "instructions": (
            "You are a Cento API worker. Return only structured JSON matching the provided schema. "
            "Do not mutate files, do not propose shell commands, and do not include secrets."
        ),
        "input": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": json.dumps(task_request, indent=2, sort_keys=True),
                    }
                ],
            }
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": output_schema_name.replace(".", "_").replace("-", "_"),
                "description": f"Cento structured worker output for {output_schema_name}.",
                "strict": True,
                "schema": schema,
            }
        },
    }
    payload["max_output_tokens"] = max_output_tokens
    return payload


def extract_output_text(response: dict[str, Any]) -> str:
    direct = response.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct
    chunks: list[str] = []
    for item in response.get("output") or []:
        if not isinstance(item, dict):
            continue
        for content in item.get("content") or []:
            if not isinstance(content, dict):
                continue
            if content.get("type") in {"output_text", "text"} and isinstance(content.get("text"), str):
                chunks.append(str(content["text"]))
            if content.get("type") == "refusal" and isinstance(content.get("refusal"), str):
                raise WorkerError("model refusal: " + str(content["refusal"]))
    text = "".join(chunks).strip()
    if not text:
        raise WorkerError("response did not contain output_text")
    return text


def estimate_cost(response: dict[str, Any] | None, profile: dict[str, Any], reserved_cost: float) -> tuple[float, dict[str, Any]]:
    usage = response.get("usage") if isinstance(response, dict) else {}
    if not isinstance(usage, dict):
        usage = {}
    input_tokens = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
    pricing = profile.get("pricing") if isinstance(profile.get("pricing"), dict) else {}
    input_rate = pricing.get("input_usd_per_1m")
    output_rate = pricing.get("output_usd_per_1m")
    if isinstance(input_rate, (int, float)) and isinstance(output_rate, (int, float)):
        cost = (input_tokens * float(input_rate) + output_tokens * float(output_rate)) / 1_000_000
        method = "usage_tokens_profile_pricing"
    elif response is None:
        cost = 0.0
        method = "not_dispatched"
    else:
        cost = max(0.0, reserved_cost)
        method = "reserved_estimate_no_pricing"
    return round(cost, 6), {
        "usage": usage,
        "pricing": pricing,
        "estimate_method": method,
    }


def write_outputs(
    out_dir: Path,
    *,
    worker_id: str,
    task_id: str,
    output_schema: str,
    owned_paths: list[str],
    content: dict[str, Any],
    status: str,
    cost_usd: float,
    cost_details: dict[str, Any],
    errors: list[str],
    started_at: str,
    response_path: Path,
    request_path: Path,
) -> dict[str, Any]:
    completed_at = now_iso()
    artifact = {
        "schema_version": SCHEMA_API_WORKER_ARTIFACT,
        "worker_id": worker_id,
        "task_id": task_id,
        "status": status,
        "artifact_type": artifact_type_for_schema(output_schema),
        "owned_paths": owned_paths,
        "content": content,
        "cost_usd_estimate": cost_usd,
        "errors": errors,
    }
    artifact_errors = validate_json_schema(artifact, api_worker_artifact_schema())
    if artifact_errors and not errors:
        artifact["status"] = "failed"
        artifact["errors"] = artifact_errors
    artifact_path = out_dir / "artifact.json"
    cost_path = out_dir / "cost_receipt.json"
    receipt_path = out_dir / "worker_receipt.json"
    write_json(artifact_path, artifact)
    cost_receipt = {
        "schema_version": "cento.api_worker_cost_receipt.v1",
        "worker_id": worker_id,
        "task_id": task_id,
        "provider": "openai",
        "cost_usd_estimate": cost_usd,
        **cost_details,
        "written_at": completed_at,
    }
    write_json(cost_path, cost_receipt)
    worker_receipt = {
        "schema_version": "cento.api_worker_receipt.v1",
        "worker_id": worker_id,
        "task_id": task_id,
        "status": artifact["status"],
        "output_schema": output_schema,
        "request": rel(request_path),
        "response": rel(response_path),
        "artifact": rel(artifact_path),
        "cost_receipt": rel(cost_path),
        "started_at": started_at,
        "completed_at": completed_at,
        "errors": artifact["errors"],
    }
    write_json(receipt_path, worker_receipt)
    return {
        "status": artifact["status"],
        "artifact": rel(artifact_path),
        "cost_receipt": rel(cost_path),
        "worker_receipt": rel(receipt_path),
        "cost_usd_estimate": cost_usd,
        "errors": artifact["errors"],
    }


def post_response(request_payload: dict[str, Any], api_key: str, timeout: int) -> dict[str, Any]:
    body = json.dumps(request_payload).encode("utf-8")
    request = urllib.request.Request(
        RESPONSES_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def command_run(args: argparse.Namespace) -> int:
    started_at = now_iso()
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    request_path = out_dir / "request.json"
    response_path = out_dir / "response.json"

    try:
        task_request = read_json(Path(args.task_request) if Path(args.task_request).is_absolute() else ROOT / args.task_request)
        config = load_api_config(Path(args.config))
        openai_config = config.get("openai") if isinstance(config.get("openai"), dict) else {}
        if openai_config and openai_config.get("enabled") is False:
            raise WorkerError("OpenAI API workers are disabled in .cento/api_workers.yaml")
        profile = profile_config(config, args.profile)
        if str(profile.get("provider") or "") != "openai":
            raise WorkerError(f"profile {args.profile} provider must be openai")
        if str(profile.get("endpoint") or "") != "responses":
            raise WorkerError(f"profile {args.profile} endpoint must be responses")
        output_schema = args.output_schema or str(profile.get("output_schema") or "")
        if output_schema not in OUTPUT_SCHEMAS:
            raise WorkerError(f"unknown output schema: {output_schema or '<missing>'}")
        model, model_env = resolve_env_value(profile.get("model"))
        request_model = model or (f"<missing env {model_env}>" if model_env else "<missing model>")
        max_input_chars = positive_int_limit(args.max_input_chars, profile, openai_config, "max_input_chars", 20_000)
        max_output_tokens = positive_int_limit(args.max_output_tokens, profile, openai_config, "max_output_tokens", 2_000)
        request_payload = build_openai_request(
            task_request,
            request_model,
            output_schema,
            max_output_tokens=max_output_tokens,
        )
        write_json(request_path, request_payload)
        request_text = str(request_payload["input"][0]["content"][0]["text"])
        if len(request_text) > max_input_chars:
            raise WorkerError(f"request input is {len(request_text)} chars, above max_input_chars={max_input_chars}")

        worker_id = str(task_request.get("worker_id") or args.worker_id)
        task_id = str(task_request.get("task_id") or task_request.get("id") or worker_id)
        owned_paths = [str(item) for item in task_request.get("write_paths") or task_request.get("owned_paths") or []]
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise WorkerError("OPENAI_API_KEY is not set")
        if not model:
            raise WorkerError(f"model is not configured; set {model_env}" if model_env else "model is not configured")

        timeout = int(args.timeout or openai_config.get("timeout_seconds") or 45)
        retry_attempts = int(args.retry_attempts if args.retry_attempts is not None else openai_config.get("retry_attempts") or 0)
        last_error = ""
        response_payload: dict[str, Any] | None = None
        for attempt in range(retry_attempts + 1):
            try:
                response_payload = post_response(request_payload, api_key, timeout)
                break
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                last_error = f"OpenAI HTTP {exc.code}: {body}"
                if exc.code < 500 and exc.code != 429:
                    break
                if attempt < retry_attempts:
                    time.sleep(min(2.0, 0.5 * (attempt + 1)))
            except (urllib.error.URLError, TimeoutError) as exc:
                last_error = f"OpenAI request failed: {exc}"
                if attempt < retry_attempts:
                    time.sleep(min(2.0, 0.5 * (attempt + 1)))
        if response_payload is None:
            write_json(response_path, {"status": "failed", "error": last_error})
            raise WorkerError(last_error or "OpenAI request failed")
        write_json(response_path, response_payload)
        if response_payload.get("status") not in {None, "completed"}:
            raise WorkerError(f"response status is not completed: {response_payload.get('status')}")
        output_text = extract_output_text(response_payload)
        try:
            content = json.loads(output_text)
        except json.JSONDecodeError as exc:
            raise WorkerError(f"structured output was not valid JSON: {exc}") from exc
        if not isinstance(content, dict):
            raise WorkerError("structured output must be a JSON object")
        schema_errors = validate_json_schema(content, OUTPUT_SCHEMAS[output_schema])
        if schema_errors:
            raise WorkerError("structured output schema validation failed: " + "; ".join(schema_errors))
        cost_usd, cost_details = estimate_cost(response_payload, profile, float(args.reserved_cost_usd or 0.0))
        cost_details["limits"] = {
            "request_input_chars": len(request_text),
            "max_input_chars": max_input_chars,
            "max_output_tokens": max_output_tokens,
        }
        result = write_outputs(
            out_dir,
            worker_id=worker_id,
            task_id=task_id,
            output_schema=output_schema,
            owned_paths=owned_paths,
            content=content,
            status="completed",
            cost_usd=cost_usd,
            cost_details=cost_details,
            errors=[],
            started_at=started_at,
            response_path=response_path,
            request_path=request_path,
        )
    except WorkerError as exc:
        task_id = args.worker_id
        worker_id = args.worker_id
        output_schema = args.output_schema or "docs_section.v1"
        owned_paths: list[str] = []
        try:
            task_request = read_json(Path(args.task_request) if Path(args.task_request).is_absolute() else ROOT / args.task_request)
            task_id = str(task_request.get("task_id") or task_request.get("id") or args.worker_id)
            worker_id = str(task_request.get("worker_id") or args.worker_id)
            owned_paths = [str(item) for item in task_request.get("write_paths") or task_request.get("owned_paths") or []]
            if not request_path.exists():
                write_json(request_path, {"status": "not_dispatched", "task_request": task_request})
        except WorkerError:
            if not request_path.exists():
                write_json(request_path, {"status": "not_dispatched"})
        if not response_path.exists():
            write_json(response_path, {"status": "failed", "error": str(exc)})
        result = write_outputs(
            out_dir,
            worker_id=worker_id,
            task_id=task_id,
            output_schema=output_schema,
            owned_paths=owned_paths,
            content={},
            status="failed",
            cost_usd=0.0,
            cost_details={"usage": {}, "pricing": {}, "estimate_method": "not_dispatched"},
            errors=[str(exc)],
            started_at=started_at,
            response_path=response_path,
            request_path=request_path,
        )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(result["artifact"])
        print(result["cost_receipt"])
    return 0 if result["status"] == "completed" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one OpenAI Responses API worker for a Cento workset.")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Call the Responses API and write structured worker artifacts.")
    run.add_argument("task_request", help="JSON request context for one workset task.")
    run.add_argument("--out-dir", required=True, help="Worker artifact output directory.")
    run.add_argument("--profile", required=True, help="API worker profile from .cento/api_workers.yaml.")
    run.add_argument("--config", default=str(DEFAULT_CONFIG), help="API worker config path.")
    run.add_argument("--output-schema", help="Override profile output schema.")
    run.add_argument("--worker-id", default="api_worker", help="Fallback worker id.")
    run.add_argument("--timeout", type=int, help="HTTP timeout in seconds.")
    run.add_argument("--retry-attempts", type=int, help="Retry attempts after the first request.")
    run.add_argument("--reserved-cost-usd", type=float, default=0.0, help="Pre-dispatch budget reservation estimate.")
    run.add_argument("--max-input-chars", type=int, help="Refuse to dispatch if serialized request input exceeds this many characters.")
    run.add_argument("--max-output-tokens", type=int, help="Responses API max_output_tokens limit.")
    run.add_argument("--json", action="store_true", help="Print JSON result.")
    run.set_defaults(func=command_run)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
