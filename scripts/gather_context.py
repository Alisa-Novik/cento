#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_JUMP = "opc@129.213.17.199"
DEFAULT_REMOTE_PORT = "2222"
DEFAULT_LINUX_SOCKET = "/tmp/cento-linux.sock"
DEFAULT_MAC_SOCKET = "/tmp/cento-mac.sock"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gather AI-ready cento context for one or two nodes.")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]), help="Cento repo root.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of Markdown.")
    parser.add_argument("--output", help="Write output to this path.")
    parser.add_argument("--no-remote", action="store_true", help="Skip SSH remote-node checks.")
    parser.add_argument("--remote", help="Remote user/host. Defaults to the opposite Cento node.")
    parser.add_argument("--jump", default=DEFAULT_JUMP, help=f"ProxyJump host. Default: {DEFAULT_JUMP}")
    parser.add_argument("--remote-port", default=DEFAULT_REMOTE_PORT, help=f"Remote SSH port. Default: {DEFAULT_REMOTE_PORT}")
    parser.add_argument("--remote-socket", help="VM Unix socket for secure mesh mode. Defaults to the opposite Cento node socket.")
    parser.add_argument("--tcp", action="store_true", help="Use the legacy VM TCP/ProxyJump path instead of Unix socket mesh.")
    parser.add_argument("--timeout", type=int, default=8, help="Per-command timeout in seconds.")
    return parser.parse_args()


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 8) -> dict[str, Any]:
    started = datetime.now(timezone.utc).isoformat()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        return {
            "cmd": cmd,
            "started": started,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "cmd": cmd,
            "started": started,
            "returncode": None,
            "stdout": (exc.stdout or "").strip() if isinstance(exc.stdout, str) else "",
            "stderr": f"timeout after {timeout}s",
        }
    except OSError as exc:
        return {
            "cmd": cmd,
            "started": started,
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
        }


def command_path(name: str) -> str | None:
    return shutil.which(name)


def command_path_any(*names: str) -> str | None:
    for name in names:
        path = command_path(name)
        if path:
            return path
    return None


def process_activity(timeout: int) -> dict[str, Any]:
    result = run(["ps", "ax", "-o", "command="], timeout=timeout)
    matches: list[str] = []
    if result["stdout"]:
        for line in result["stdout"].splitlines():
            lowered = line.lower()
            if "codex" in lowered and "gather_context.py" not in lowered:
                matches.append(line.strip())
    return {
        "state": "executing agent" if matches else "idle",
        "summary": matches[0] if matches else "idle",
        "count": len(matches),
    }


def apple_watch_status(timeout: int) -> dict[str, Any]:
    if current_platform() != "macos":
        return {"name": "apple watch", "connection": "unknown", "activity": "idle", "detail": "not local macos"}
    result = run(["system_profiler", "SPBluetoothDataType", "-json"], timeout=min(timeout, 4))
    if result["returncode"] != 0:
        return {"name": "apple watch", "connection": "unknown", "activity": "idle", "detail": result["stderr"] or "bluetooth query failed"}
    try:
        payload = json.loads(result["stdout"] or "{}")
    except json.JSONDecodeError:
        return {"name": "apple watch", "connection": "unknown", "activity": "idle", "detail": "bluetooth output was not json"}

    for group_name, connection in [("device_connected", "connected"), ("device_not_connected", "disconnected")]:
        for controller in payload.get("SPBluetoothDataType", []):
            for item in controller.get(group_name, []) or []:
                for name, data in item.items():
                    if "watch" in name.lower():
                        rssi = data.get("device_rssi")
                        detail = f"rssi {rssi}" if rssi else "paired"
                        return {"name": name, "connection": connection, "activity": "idle", "detail": detail}
    return {"name": "apple watch", "connection": "unknown", "activity": "idle", "detail": "not found in bluetooth devices"}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def current_platform() -> str:
    system = platform.system()
    if system == "Darwin":
        return "macos"
    if system == "Linux":
        return "linux"
    return system.lower()


def tool_summary(root: Path) -> dict[str, Any]:
    tools_path = root / "data" / "tools.json"
    if not tools_path.exists():
        return {"error": f"missing {tools_path}"}
    tools = read_json(tools_path).get("tools", [])
    summary: dict[str, Any] = {
        "count": len(tools),
        "macos": [],
        "linux": [],
        "both": [],
        "linux_only": [],
        "macos_only": [],
    }
    for tool in sorted(tools, key=lambda item: item["id"]):
        platforms = tool.get("platforms") or ["linux", "macos"]
        tool_id = tool["id"]
        if "macos" in platforms:
            summary["macos"].append(tool_id)
        if "linux" in platforms:
            summary["linux"].append(tool_id)
        if "macos" in platforms and "linux" in platforms:
            summary["both"].append(tool_id)
        elif "linux" in platforms:
            summary["linux_only"].append(tool_id)
        elif "macos" in platforms:
            summary["macos_only"].append(tool_id)
    return summary


def local_context(root: Path, timeout: int) -> dict[str, Any]:
    env_mcp = root / ".env.mcp"
    wrappers = {name: str(Path.home() / "bin" / name) for name in ["cento", "codex-bt-audio-doctor", "codex-kitty-theme"]}
    commands = {name: command_path(name) for name in ["cento", "bash", "python3", "go", "node", "npm", "npx", "ssh", "rg", "fzf", "jq", "kitty", "tmux"]}
    commands["fd"] = command_path_any("fd", "fdfind")
    if not commands["cento"] and Path(wrappers["cento"]).exists():
        commands["cento"] = wrappers["cento"]
    cento_cmd = commands["cento"] or str(root / "scripts" / "cento.sh")
    return {
        "host": {
            "hostname": socket.gethostname(),
            "platform": current_platform(),
            "system": platform.platform(),
            "user": os.environ.get("USER") or os.environ.get("LOGNAME"),
            "home": str(Path.home()),
        },
        "repo": {
            "root": str(root),
            "exists": root.exists(),
            "git_status": run(["git", "status", "--short", "--branch"], root, timeout),
            "git_remote": run(["git", "remote", "-v"], root, timeout),
            "head": run(["git", "rev-parse", "--short", "HEAD"], root, timeout),
        },
        "commands": commands,
        "wrappers": wrappers,
        "config": {
            "cento_config": str(Path.home() / ".config" / "cento"),
            "env_mcp": str(env_mcp),
            "env_mcp_exists": env_mcp.exists(),
            "cento_root_env": os.environ.get("CENTO_ROOT"),
            "github_token_present": bool(os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN")),
        },
        "tools": tool_summary(root),
        "platform_report": run([sys.executable, str(root / "scripts" / "platform_report.py"), "--registry", str(root / "data" / "tools.json")], root, timeout),
        "health": {
            "tmux": run(["tmux", "ls"], timeout=timeout) if commands.get("tmux") else {"returncode": None, "stdout": "", "stderr": "tmux missing"},
            "mesh_status": run([cento_cmd, "bridge", "mesh-status"], root, timeout),
            "linux_bridge_service": run(["systemctl", "--user", "is-active", "cento-bridge-linux.service"], timeout=timeout) if current_platform() == "linux" and command_path("systemctl") else {"returncode": None, "stdout": "", "stderr": "not linux/systemd"},
            "activity": process_activity(timeout),
            "apple_watch": apple_watch_status(timeout),
        },
    }


def default_remote_for_platform(local_platform: str) -> tuple[str, str, str]:
    if local_platform == "linux":
        return "anovik-air@cento-mac", DEFAULT_MAC_SOCKET, "/Users/anovik-air/bin/cento gather-context --no-remote | head -90"
    return "alice@cento-linux", DEFAULT_LINUX_SOCKET, '/home/alice/bin/cento gather-context --no-remote | head -90'


def remote_context(remote: str, jump: str, port: str, socket_path: str, use_tcp: bool, timeout: int) -> dict[str, Any]:
    remote_script = r'''
set -eu
printf 'hostname=%s\n' "$(hostname)"
printf 'user=%s\n' "$(whoami)"
printf 'home=%s\n' "$HOME"
repo=""
if [ -d "$HOME/projects/cento/.git" ]; then
  repo="$HOME/projects/cento"
elif [ -d "$HOME/cento/.git" ]; then
  repo="$HOME/cento"
fi
if [ -n "$repo" ]; then
  printf 'repo=%s\n' "$repo"
  git -C "$repo" status --short --branch | head -1 | sed 's/^/git_status=/'
  git -C "$repo" rev-parse --short HEAD 2>/dev/null | sed 's/^/git_head=/'
  printf 'git_dirty_count=%s\n' "$(git -C "$repo" status --short 2>/dev/null | wc -l | tr -d ' ')"
else
  printf 'repo=missing\n'
fi
if command -v cento >/dev/null 2>&1; then
  printf 'cento=%s\n' "$(command -v cento)"
  cento --help | head -1 | sed 's/^/cento_help=/'
elif [ -x "$HOME/bin/cento" ]; then
  printf 'cento=%s\n' "$HOME/bin/cento"
  "$HOME/bin/cento" --help | head -1 | sed 's/^/cento_help=/'
else
  printf 'cento=missing\n'
fi
for cmd in bash python3 go node npm npx ssh rg fzf jq; do
  if command -v "$cmd" >/dev/null 2>&1; then
    printf 'cmd_%s=%s\n' "$cmd" "$(command -v "$cmd")"
  else
    printf 'cmd_%s=\n' "$cmd"
  fi
done
if command -v fd >/dev/null 2>&1; then
  printf 'cmd_fd=%s\n' "$(command -v fd)"
elif command -v fdfind >/dev/null 2>&1; then
  printf 'cmd_fd=%s\n' "$(command -v fdfind)"
else
  printf 'cmd_fd=\n'
fi
if command -v tmux >/dev/null 2>&1; then
  printf 'tmux=%s\n' "$(tmux ls 2>&1 | head -5 | tr '\n' ';' | sed 's/;*$//')"
else
  printf 'tmux=missing\n'
fi
if command -v systemctl >/dev/null 2>&1; then
  systemctl --user is-active cento-bridge-linux.service 2>&1 | head -1 | sed 's/^/linux_bridge_service=/'
fi
agent="$(ps ax -o command= 2>/dev/null | awk 'tolower($0) ~ /codex/ && $0 !~ /awk/ {print}' | head -5 | tr '\n' ';' | sed 's/;*$//')"
if [ -n "$agent" ]; then
  printf 'activity=executing agent\n'
  printf 'activity_detail=%s\n' "$agent"
else
  printf 'activity=idle\n'
  printf 'activity_detail=idle\n'
fi
'''
    if use_tcp:
        cmd = [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=accept-new",
            "-o",
            f"ConnectTimeout={timeout}",
            "-J",
            jump,
            "-p",
            port,
            remote,
            remote_script,
        ]
    else:
        cmd = [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=accept-new",
            "-o",
            f"ConnectTimeout={timeout}",
            "-o",
            f"ProxyCommand=ssh {jump} nc -U {socket_path}",
            remote,
            remote_script,
        ]
    result = run(cmd, timeout=timeout + 2)
    parsed: dict[str, str] = {}
    if result["stdout"]:
        for line in result["stdout"].splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                parsed[key] = value
    return {"connection": {"remote": remote, "jump": jump, "port": port, "socket": socket_path, "transport": "tcp" if use_tcp else "socket"}, "raw": result, "parsed": parsed}


def render_markdown(payload: dict[str, Any]) -> str:
    local = payload["local"]
    lines = [
        "# Cento Context",
        "",
        f"Generated: `{payload['generated_at']}`",
        "",
        "## Local Node",
        "",
        f"- host: `{local['host']['hostname']}`",
        f"- platform: `{local['host']['platform']}`",
        f"- user: `{local['host']['user']}`",
        f"- repo: `{local['repo']['root']}`",
        f"- git: `{local['repo']['git_status']['stdout'].splitlines()[0] if local['repo']['git_status']['stdout'] else 'unknown'}`",
        "",
        "## Command Paths",
        "",
    ]
    for name, path in local["commands"].items():
        lines.append(f"- `{name}`: `{path or 'missing'}`")

    tools = local["tools"]
    lines.extend([
        "",
        "## Platform Support",
        "",
        f"- total tools: `{tools.get('count', 0)}`",
        f"- macOS tools: `{len(tools.get('macos', []))}`",
        f"- Linux tools: `{len(tools.get('linux', []))}`",
        f"- both: `{', '.join(tools.get('both', []))}`",
        f"- Linux only: `{', '.join(tools.get('linux_only', [])) or 'none'}`",
        f"- macOS only: `{', '.join(tools.get('macos_only', [])) or 'none'}`",
        "",
        "## Integration State",
        "",
        f"- `.env.mcp`: `{local['config']['env_mcp']}` exists=`{local['config']['env_mcp_exists']}`",
        f"- `CENTO_ROOT` env: `{local['config']['cento_root_env'] or 'unset'}`",
        f"- GitHub token present: `{local['config']['github_token_present']}`",
    ])

    remote = payload.get("remote")
    if remote:
        lines.extend(["", "## Remote Node", ""])
        parsed = remote.get("parsed", {})
        raw = remote.get("raw", {})
        if remote["connection"].get("transport") == "socket":
            lines.append(f"- ssh: `{remote['connection']['remote']}` via `{remote['connection']['jump']}` socket `{remote['connection']['socket']}`")
        else:
            lines.append(f"- ssh: `{remote['connection']['remote']}` via `{remote['connection']['jump']}` port `{remote['connection']['port']}`")
        lines.append(f"- status: `{raw.get('returncode')}`")
        for key in ["hostname", "user", "home", "repo", "git_status", "cento", "cento_help"]:
            if key in parsed:
                lines.append(f"- `{key}`: `{parsed[key]}`")
        if raw.get("stderr"):
            lines.extend(["", "Remote stderr:", "", "```", raw["stderr"], "```"])

    lines.extend([
        "",
        "## Agent Notes",
        "",
        "- Treat `data/tools.json` as the platform source of truth.",
        "- Use `cento platforms macos` or `cento platforms linux` before running platform-sensitive tools.",
        "- Use `cento bridge check` or this gather output before assuming the other node is reachable.",
        "- Keep `.env.mcp` machine-local; do not copy secrets between nodes.",
    ])
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    root = Path(args.root).expanduser().resolve()
    payload: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "local": local_context(root, args.timeout),
    }
    if not args.no_remote:
        local_platform = payload["local"]["host"]["platform"]
        default_remote, default_socket, _default_command = default_remote_for_platform(local_platform)
        remote = args.remote or default_remote
        socket_path = args.remote_socket or default_socket
        payload["remote"] = remote_context(remote, args.jump, args.remote_port, socket_path, args.tcp, args.timeout)

    text = json.dumps(payload, indent=2) + "\n" if args.json else render_markdown(payload)
    if args.output:
        output = Path(args.output).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text)
        print(output)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
