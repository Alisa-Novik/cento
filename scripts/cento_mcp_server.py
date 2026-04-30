#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TIMEOUT = int(os.environ.get("CENTO_MCP_TIMEOUT") or "30")
READ_ONLY = os.environ.get("CENTO_MCP_READ_ONLY", "").strip().lower() in {"1", "true", "yes", "on"}


class ToolError(Exception):
    pass


def root_relative(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    resolved = path.resolve()
    try:
        resolved.relative_to(ROOT)
    except ValueError as exc:
        raise ToolError(f"path is outside Cento repo: {value}") from exc
    return resolved


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def cento_cmd(*args: str) -> list[str]:
    script = ROOT / "scripts" / "cento.sh"
    if script.exists():
        return ["bash", str(script), *args]
    return ["cento", *args]


def run_command(command: list[str], *, timeout: int | None = None) -> dict[str, Any]:
    proc = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout or DEFAULT_TIMEOUT,
        check=False,
    )
    return {
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "command": command,
        "cwd": str(ROOT),
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def ensure_write_allowed() -> None:
    if READ_ONLY:
        raise ToolError("Cento MCP is read-only because CENTO_MCP_READ_ONLY is enabled")


def optional_bool(args: dict[str, Any], key: str, default: bool = False) -> bool:
    value = args.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def tool_context(args: dict[str, Any]) -> dict[str, Any]:
    command = ["python3", str(ROOT / "scripts" / "gather_context.py")]
    if not optional_bool(args, "remote", False):
        command.append("--no-remote")
    if optional_bool(args, "json", False):
        command.append("--json")
    return run_command(command, timeout=int(args.get("timeout", DEFAULT_TIMEOUT)))


def tool_platforms(args: dict[str, Any]) -> dict[str, Any]:
    command = cento_cmd("platforms")
    platform = str(args.get("platform") or "").strip()
    if platform:
        if platform not in {"linux", "macos"}:
            raise ToolError("platform must be linux or macos")
        command.append(platform)
    if optional_bool(args, "markdown", False):
        command.append("--markdown")
    return run_command(command)


def tool_cluster_status(args: dict[str, Any]) -> dict[str, Any]:
    return run_command(cento_cmd("cluster", "status"), timeout=int(args.get("timeout", DEFAULT_TIMEOUT)))


def tool_bridge_mesh_status(args: dict[str, Any]) -> dict[str, Any]:
    return run_command(cento_cmd("bridge", "mesh-status"), timeout=int(args.get("timeout", DEFAULT_TIMEOUT)))


def tool_agent_work_list(args: dict[str, Any]) -> dict[str, Any]:
    command = cento_cmd("agent-work", "list")
    status = str(args.get("status") or "").strip()
    if status:
        command.extend(["--status", status])
    return run_command(command)


def tool_agent_work_show(args: dict[str, Any]) -> dict[str, Any]:
    issue = str(args.get("issue") or "").strip()
    if not issue:
        raise ToolError("issue is required")
    return run_command(cento_cmd("agent-work", "show", issue))


def tool_agent_work_create(args: dict[str, Any]) -> dict[str, Any]:
    ensure_write_allowed()
    title = str(args.get("title") or "").strip()
    if not title:
        raise ToolError("title is required")
    command = cento_cmd("agent-work", "create", "--title", title, "--json")
    for key in ("description", "node", "agent", "role", "package"):
        value = str(args.get(key) or "").strip()
        if value:
            command.extend([f"--{key}", value])
    return run_command(command, timeout=int(args.get("timeout", DEFAULT_TIMEOUT)))


def tool_agent_work_claim(args: dict[str, Any]) -> dict[str, Any]:
    ensure_write_allowed()
    issue = str(args.get("issue") or "").strip()
    if not issue:
        raise ToolError("issue is required")
    command = cento_cmd("agent-work", "claim", issue)
    for key in ("node", "agent", "role", "note"):
        value = str(args.get(key) or "").strip()
        if value:
            command.extend([f"--{key}", value])
    return run_command(command, timeout=int(args.get("timeout", DEFAULT_TIMEOUT)))


def tool_agent_work_update(args: dict[str, Any]) -> dict[str, Any]:
    ensure_write_allowed()
    issue = str(args.get("issue") or "").strip()
    if not issue:
        raise ToolError("issue is required")
    command = cento_cmd("agent-work", "update", issue)
    for key in ("status", "node", "agent", "role", "note"):
        value = str(args.get(key) or "").strip()
        if value:
            command.extend([f"--{key}", value])
    return run_command(command, timeout=int(args.get("timeout", DEFAULT_TIMEOUT)))


def tool_agent_work_handoff(args: dict[str, Any]) -> dict[str, Any]:
    ensure_write_allowed()
    issue = str(args.get("issue") or "").strip()
    if not issue:
        raise ToolError("issue is required")
    command = cento_cmd("agent-work", "handoff", issue)
    for key in ("summary", "risk", "manifest", "run-dir", "output", "note", "node", "agent"):
        value = str(args.get(key.replace("-", "_")) or args.get(key) or "").strip()
        if value:
            if key in {"manifest", "output"}:
                root_relative(value)
            command.extend([f"--{key}", value])
    for key in ("changed_file", "command", "evidence"):
        flag = "--changed-file" if key == "changed_file" else f"--{key}"
        values = args.get(key) or []
        if isinstance(values, str):
            values = [values]
        for value in values:
            text = str(value).strip()
            if text:
                if key in {"changed_file", "evidence"}:
                    root_relative(text)
                command.extend([flag, text])
    return run_command(command, timeout=int(args.get("timeout", DEFAULT_TIMEOUT)))


def tool_agent_work_validate_run(args: dict[str, Any]) -> dict[str, Any]:
    no_update = optional_bool(args, "no_update", False)
    if not no_update:
        ensure_write_allowed()
    issue = str(args.get("issue") or "").strip()
    if not issue:
        raise ToolError("issue is required")
    command = cento_cmd("agent-work", "validate-run", issue)
    for key in ("manifest", "note", "node", "agent"):
        value = str(args.get(key) or "").strip()
        if value:
            if key == "manifest":
                root_relative(value)
            command.extend([f"--{key}", value])
    if no_update:
        command.append("--no-update")
    return run_command(command, timeout=int(args.get("timeout", DEFAULT_TIMEOUT)))


def tool_story_manifest_validate(args: dict[str, Any]) -> dict[str, Any]:
    manifest = str(args.get("manifest") or "").strip()
    if not manifest:
        raise ToolError("manifest is required")
    path = root_relative(manifest)
    command = ["python3", str(ROOT / "scripts" / "story_manifest.py"), "validate", rel(path)]
    if optional_bool(args, "check_links", False):
        command.append("--check-links")
    if optional_bool(args, "json", False):
        command.append("--json")
    return run_command(command)


def tool_story_manifest_render_hub(args: dict[str, Any]) -> dict[str, Any]:
    check_only = optional_bool(args, "check_only", False)
    if not check_only:
        ensure_write_allowed()
    manifest = str(args.get("manifest") or "").strip()
    if not manifest:
        raise ToolError("manifest is required")
    path = root_relative(manifest)
    command = ["python3", str(ROOT / "scripts" / "story_manifest.py"), "render-hub", rel(path)]
    for key in ("deliverables", "output"):
        value = str(args.get(key) or "").strip()
        if value:
            root_relative(value)
            command.extend([f"--{key}", value])
    if optional_bool(args, "check_links", False):
        command.append("--check-links")
    if check_only:
        command.append("--check-only")
    if optional_bool(args, "json", False):
        command.append("--json")
    return run_command(command)


def schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required or [], "additionalProperties": False}


ToolFunc = Callable[[dict[str, Any]], dict[str, Any]]


TOOLS: dict[str, tuple[str, dict[str, Any], ToolFunc, bool]] = {
    "cento_context": (
        "Gather local or local+remote Cento context.",
        schema({"remote": {"type": "boolean"}, "json": {"type": "boolean"}, "timeout": {"type": "integer", "minimum": 1}}),
        tool_context,
        False,
    ),
    "cento_platforms": (
        "Report Cento platform support from data/tools.json.",
        schema({"platform": {"type": "string", "enum": ["linux", "macos"]}, "markdown": {"type": "boolean"}}),
        tool_platforms,
        False,
    ),
    "cento_cluster_status": (
        "Show Cento cluster status.",
        schema({"timeout": {"type": "integer", "minimum": 1}}),
        tool_cluster_status,
        False,
    ),
    "cento_bridge_mesh_status": (
        "Show secure bridge mesh socket status.",
        schema({"timeout": {"type": "integer", "minimum": 1}}),
        tool_bridge_mesh_status,
        False,
    ),
    "cento_agent_work_list": (
        "List Redmine-backed Cento agent-work issues.",
        schema({"status": {"type": "string"}}),
        tool_agent_work_list,
        False,
    ),
    "cento_agent_work_show": (
        "Show one Redmine-backed Cento agent-work issue.",
        schema({"issue": {"type": "integer"}}, ["issue"]),
        tool_agent_work_show,
        False,
    ),
    "cento_agent_work_create": (
        "Create a Cento agent-work issue. This is an explicit write tool.",
        schema(
            {
                "title": {"type": "string"},
                "description": {"type": "string"},
                "node": {"type": "string"},
                "agent": {"type": "string"},
                "role": {"type": "string", "enum": ["builder", "validator", "coordinator"]},
                "package": {"type": "string"},
                "timeout": {"type": "integer", "minimum": 1},
            },
            ["title"],
        ),
        tool_agent_work_create,
        True,
    ),
    "cento_agent_work_claim": (
        "Claim an agent-work issue. This is an explicit write tool.",
        schema(
            {
                "issue": {"type": "integer"},
                "node": {"type": "string"},
                "agent": {"type": "string"},
                "role": {"type": "string", "enum": ["builder", "validator", "coordinator"]},
                "note": {"type": "string"},
                "timeout": {"type": "integer", "minimum": 1},
            },
            ["issue"],
        ),
        tool_agent_work_claim,
        True,
    ),
    "cento_agent_work_update": (
        "Update status/metadata/note for an agent-work issue. This is an explicit write tool.",
        schema(
            {
                "issue": {"type": "integer"},
                "status": {"type": "string"},
                "node": {"type": "string"},
                "agent": {"type": "string"},
                "role": {"type": "string", "enum": ["builder", "validator", "coordinator"]},
                "note": {"type": "string"},
                "timeout": {"type": "integer", "minimum": 1},
            },
            ["issue"],
        ),
        tool_agent_work_update,
        True,
    ),
    "cento_agent_work_handoff": (
        "Write a builder handoff report and move an issue to validation. This is an explicit write tool.",
        schema(
            {
                "issue": {"type": "integer"},
                "summary": {"type": "string"},
                "changed_file": {"type": "array", "items": {"type": "string"}},
                "command": {"type": "array", "items": {"type": "string"}},
                "evidence": {"type": "array", "items": {"type": "string"}},
                "risk": {"type": "string"},
                "manifest": {"type": "string"},
                "run_dir": {"type": "string"},
                "output": {"type": "string"},
                "note": {"type": "string"},
                "node": {"type": "string"},
                "agent": {"type": "string"},
                "timeout": {"type": "integer", "minimum": 1},
            },
            ["issue"],
        ),
        tool_agent_work_handoff,
        True,
    ),
    "cento_agent_work_validate_run": (
        "Run validation.json checks and record validator result. This is an explicit write tool unless no_update is true.",
        schema(
            {
                "issue": {"type": "integer"},
                "manifest": {"type": "string"},
                "note": {"type": "string"},
                "node": {"type": "string"},
                "agent": {"type": "string"},
                "no_update": {"type": "boolean"},
                "timeout": {"type": "integer", "minimum": 1},
            },
            ["issue"],
        ),
        tool_agent_work_validate_run,
        True,
    ),
    "cento_story_manifest_validate": (
        "Validate a story.json manifest.",
        schema({"manifest": {"type": "string"}, "check_links": {"type": "boolean"}, "json": {"type": "boolean"}}, ["manifest"]),
        tool_story_manifest_validate,
        False,
    ),
    "cento_story_manifest_render_hub": (
        "Generate deliverables.json and start-here.html from story.json. This is an explicit write tool.",
        schema(
            {
                "manifest": {"type": "string"},
                "deliverables": {"type": "string"},
                "output": {"type": "string"},
                "check_links": {"type": "boolean"},
                "check_only": {"type": "boolean"},
                "json": {"type": "boolean"},
            },
            ["manifest"],
        ),
        tool_story_manifest_render_hub,
        True,
    ),
}


def respond(message_id: Any, result: Any = None, error: dict[str, Any] | None = None) -> None:
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": message_id}
    if error is not None:
        payload["error"] = error
    else:
        payload["result"] = result
    sys.stdout.write(json.dumps(payload, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def tool_list() -> list[dict[str, Any]]:
    tools = []
    for name, (description, input_schema, _func, writes) in sorted(TOOLS.items()):
        suffix = " Disabled when CENTO_MCP_READ_ONLY=1." if writes else ""
        tools.append({"name": name, "description": description + suffix, "inputSchema": input_schema})
    return tools


def handle(message: dict[str, Any]) -> None:
    message_id = message.get("id")
    method = message.get("method")
    if message_id is None and str(method).startswith("notifications/"):
        return

    try:
        if method == "initialize":
            respond(
                message_id,
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "cento", "version": "0.1.0"},
                },
            )
        elif method == "ping":
            respond(message_id, {})
        elif method == "tools/list":
            respond(message_id, {"tools": tool_list()})
        elif method == "tools/call":
            params = message.get("params") or {}
            name = str(params.get("name") or "")
            arguments = params.get("arguments") or {}
            if name not in TOOLS:
                raise ToolError(f"unknown tool: {name}")
            _description, _schema, func, _writes = TOOLS[name]
            result = func(arguments if isinstance(arguments, dict) else {})
            respond(message_id, {"content": [{"type": "text", "text": json.dumps(result, indent=2)}], "isError": not result.get("ok", True)})
        elif method in {"resources/list", "prompts/list"}:
            respond(message_id, {method.split("/", 1)[0]: []})
        else:
            respond(message_id, error={"code": -32601, "message": f"method not found: {method}"})
    except subprocess.TimeoutExpired as exc:
        respond(message_id, error={"code": -32000, "message": f"command timed out after {exc.timeout}s"})
    except (ToolError, ValueError) as exc:
        respond(message_id, error={"code": -32000, "message": str(exc)})
    except Exception as exc:  # pragma: no cover - defensive MCP boundary
        respond(message_id, error={"code": -32603, "message": f"internal error: {exc}"})


def run_stdio() -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            respond(None, error={"code": -32700, "message": f"parse error: {exc}"})
            continue
        if isinstance(message, list):
            for item in message:
                if isinstance(item, dict):
                    handle(item)
        elif isinstance(message, dict):
            handle(message)
    return 0


def run_list_tools() -> int:
    print(json.dumps({"tools": tool_list(), "read_only": READ_ONLY, "root": str(ROOT)}, indent=2))
    return 0


def run_call_tool(name: str, arguments: str) -> int:
    if name not in TOOLS:
        raise SystemExit(f"unknown tool: {name}")
    payload = json.loads(arguments or "{}")
    if not isinstance(payload, dict):
        raise SystemExit("arguments must be a JSON object")
    try:
        result = TOOLS[name][2](payload)
    except ToolError as exc:
        result = {"ok": False, "error": str(exc)}
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok", False) else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Cento MCP stdio server and local smoke-test helper.")
    parser.add_argument("--list-tools", action="store_true", help="Print MCP tool metadata and exit.")
    parser.add_argument("--call-tool", help="Call one tool directly for smoke testing.")
    parser.add_argument("--arguments", default="{}", help="JSON object used with --call-tool.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.list_tools:
        return run_list_tools()
    if args.call_tool:
        return run_call_tool(args.call_tool, args.arguments)
    return run_stdio()


if __name__ == "__main__":
    raise SystemExit(main())
