#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import select
import signal
import shutil
import subprocess
import platform
import sys
import termios
import textwrap
import time
import tty
import unicodedata
import shlex
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from industrial_activity import build_activity_events, classify_severity, dedupe_sort_events, event, filter_activity_events, load_agent_work_payload, parse_timestamp
from industrial_status import metrics
from jobs_server import load_jobs
from network_web_server import build_cluster_panel_model, cluster_snapshot


ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_ROOT = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "cento"
DATA_ROOT = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "cento" / "industrial-os"
LOG_ROOT = ROOT_DIR / "logs"
WALLPAPER = DATA_ROOT / "wallpaper.png"
DEFAULT_HERO_ART = ROOT_DIR / "assets" / "industrial-os" / "volcano-pane.png"
HERO_ART = Path(os.environ.get("CENTO_INDUSTRIAL_HERO_ART", DEFAULT_HERO_ART))
HERO_HAS_KITTY_BACKGROUND = os.environ.get("CENTO_INDUSTRIAL_HERO_BACKGROUND", "0") == "1"
ORANGE = "\033[38;5;202m"
AMBER = "\033[38;5;214m"
GREEN = "\033[38;5;114m"
MUTED = "\033[38;5;180m"
TEXT = "\033[38;5;230m"
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
BLUE = "\033[38;5;109m"
WHITE = "\033[38;5;223m"
HERO_BG = "\033[48;5;16m"
HERO_BG_SOFT = "\033[48;5;52m"
PANEL_WIDTH = 58
UPPER_HALF_BLOCK = "\u2580"
ALT_SCREEN = "\033[?1049h"
MAIN_SCREEN = "\033[?1049l"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"
HOME = "\033[H"
CLEAR_TO_END = "\033[J"
CLEAR_LINE = "\033[K"
HERO_QUEUE = [
    {
        "title": "Finish industrial dashboard",
        "detail": "replace hero pane with mission model",
        "group": "BUILD",
        "key": "a",
        "command": ["python3", "-m", "py_compile", "scripts/industrial_panel.py"],
    },
    {
        "title": "Review funnel docs",
        "detail": "extract blockers + next owner",
        "group": "DOCS",
        "key": "o",
        "command": ["python3", "scripts/funnel_check.py"],
    },
    {
        "title": "Run make check",
        "detail": "execute test pack, capture failure",
        "group": "VERIFY",
        "key": "m",
        "command": ["make", "check"],
    },
    {
        "title": "Draft demo follow-up",
        "detail": "6-line Slack update + ask",
        "group": "ADOPT",
        "key": "u",
        "command": None,
    },
    {
        "title": "Turn repeated step into job",
        "detail": "scaffold job from command history",
        "group": "AUTO",
        "key": "g",
        "command": ["python3", "scripts/cluster_job_runner.py", "--help"],
    },
]
HERO_READY_ACTIONS = 12
def normalize_platform_name(value: str) -> str:
    value = value.lower()
    if value == "darwin":
        return "macos"
    return value


ACTION_PLATFORM = normalize_platform_name(platform.system())
ACTION_REGISTRY = ROOT_DIR / "data" / "industrial-actions.json"
ACTION_FIXTURE = os.environ.get("CENTO_INDUSTRIAL_ACTIONS_FIXTURE", "").strip()
CLUSTER_FIXTURE = os.environ.get("CENTO_INDUSTRIAL_CLUSTER_FIXTURE", "").strip()
ACTIVITY_FIXTURE = os.environ.get("CENTO_INDUSTRIAL_ACTIVITY_FIXTURE", "").strip()
SAFE_ACTION_COMMANDS = {"./scripts/cento.sh", "cento", "python", "python3", sys.executable}
UNSAFE_ACTION_COMMANDS = {"sh", "bash", "zsh", "fish", "ksh", "csh", "tcsh", "dash"}
ACTIVITY_RENDER_OPTIONS: dict[str, Any] = {
    "limit": 14,
    "sources": [],
    "severities": [],
    "query": "",
}
HERO_STATE: dict[str, Any] = {
    "selected": 0,
    "message": "implement action router",
    "output": ["j/k or arrows move", "a or enter runs selected action", "o opens context", "u drafts update"],
    "last_key": "",
}
ACTIONS_STATE: dict[str, Any] = {
    "selected": 0,
    "running": None,
    "message": "ready",
    "output": ["j/k or arrows move", "1-5 select", "enter runs selected action", "d dry-runs selected action", "q quits panel"],
    "last_key": "",
    "results": {},
}
ACTIONS_STATE_LOCK = threading.Lock()
JOBS_STATE: dict[str, Any] = {
    "selected": 0,
    "message": "ready",
    "output": ["j/k or arrows move", "1-9 select", "q quits panel"],
    "last_key": "",
}


def term_size() -> tuple[int, int]:
    size = shutil.get_terminal_size((96, 28))
    return size.columns, size.lines


def clear() -> None:
    print("\033[2J\033[H", end="")


def render_frame(panel: str) -> str:
    frame = io.StringIO()
    with contextlib.redirect_stdout(frame):
        if panel != "hero":
            print(f"{MUTED}{datetime.now().strftime('%H:%M:%S')}  {panel}{RESET}")
        RENDERERS[panel]()
    return frame.getvalue()


def paint_frame(frame: str) -> None:
    lines = frame.splitlines()
    output = [HOME]
    if lines:
        output.extend(f"{line}{CLEAR_LINE}\n" for line in lines)
    output.append(CLEAR_TO_END)
    sys.stdout.write("".join(output))
    sys.stdout.flush()


def enter_live_display() -> None:
    sys.stdout.write(f"{ALT_SCREEN}{HIDE_CURSOR}\033[2J{HOME}")
    sys.stdout.flush()


def leave_live_display() -> None:
    sys.stdout.write(f"{SHOW_CURSOR}{MAIN_SCREEN}")
    sys.stdout.flush()


def title(text: str) -> None:
    print(f"{ORANGE}{BOLD}> {text.upper()}{RESET}")
    print(f"{MUTED}{'-' * min(term_size()[0], 96)}{RESET}")


def bar(label: str, value: int, width: int = 26) -> str:
    value = max(0, min(100, value))
    filled = round(width * value / 100)
    return f"{label:<7} {ORANGE}{'#' * filled}{MUTED}{'.' * (width - filled)}{RESET} {value:>3}%"


def styled(text: str, color: str = TEXT, bold: bool = False, dim: bool = False) -> str:
    weight = BOLD if bold else ""
    shade = DIM if dim else ""
    return f"{color}{weight}{shade}{text}{RESET}"


def cell_text(text: str, width: int, align: str = "left") -> str:
    plain = clip_text(text, width)
    padding = max(0, width - visible_len(plain))
    if align == "right":
        return " " * padding + plain
    if align == "center":
        left = padding // 2
        return " " * left + plain + " " * (padding - left)
    return plain + " " * padding


def ansi_cell(value: str, width: int, align: str = "left") -> str:
    visible = visible_len(value)
    if visible > width:
        value = clip_text(value, width)
        visible = visible_len(value)
    padding = max(0, width - visible)
    if align == "right":
        return " " * padding + value
    if align == "center":
        left = padding // 2
        return " " * left + value + " " * (padding - left)
    return value + " " * padding


def badge(text: str, fg: str = AMBER, bg: str = "") -> str:
    return f"{bg}{fg}{BOLD}[{text}]{RESET}"


def bg_fill(value: str, bg: str = HERO_BG) -> str:
    return bg + value.replace(RESET, RESET + bg) + RESET


def hero_row(content: str, width: int, border: str = "║", bg: str = HERO_BG) -> str:
    inner = max(1, width - 4)
    return f"{ORANGE}{border}{RESET}{bg_fill(' ' + ansi_cell(content, inner) + ' ', bg)}{ORANGE}{border}{RESET}"


def draw_panel(title_text: str, body: list[str], width: int, mark: str = "▪", tag: str = "") -> None:
    width = max(24, width)
    inner = width - 2
    print(f"{ORANGE}┌{'─' * (width - 2)}┐{RESET}")
    title_value = f" {mark} {title_text.upper()}"
    header = styled(title_value, ORANGE, bold=True)
    if tag:
        tag_value = badge(tag)
        available = max(0, inner - visible_len(title_value) - visible_len(tag_value) - 1)
        print(f"{ORANGE}│{RESET}{header}{' ' * available} {tag_value}{ORANGE}│{RESET}")
    else:
        print(f"{ORANGE}│{RESET}{ansi_cell(header, inner)}{ORANGE}│{RESET}")
    for line in body:
        print(f"{ORANGE}│{RESET} {ansi_cell(line, inner - 1)}{ORANGE}│{RESET}")
    print(f"{ORANGE}└{'─' * (width - 2)}┘{RESET}")


def mission_row(label: str, value: str, width: int, color: str = TEXT) -> list[str]:
    label_width = 14
    value_width = max(20, width - label_width - 3)
    wrapped = textwrap.wrap(value, value_width) or [""]
    lines = []
    for index, part in enumerate(wrapped[:2]):
        prefix = styled(cell_text(label if index == 0 else "", label_width), AMBER, bold=True)
        lines.append(f" {prefix}  {styled(part, color)}")
    return lines


def queue_row(index: int, title_text: str, detail: str, group: str, key: str, width: int, active: bool = False) -> str:
    marker = styled("▌", ORANGE, bold=True) if active else " "
    number = styled(str(index), AMBER, bold=True)
    group_badge = badge(group)
    fixed = 9 + visible_len(group_badge)
    title_width = max(16, width - fixed)
    top = f"{marker} {number}  {styled(cell_text(title_text, title_width), TEXT, bold=True)} {group_badge}"
    key_line = styled(f"NEXT: {clip_text(detail, max(10, width - 14))}", MUTED)
    shortcut = styled(f"[{key}]", ORANGE, bold=True)
    return lip_join([top, f"     {key_line}{' ' * max(1, width - visible_len(key_line) - 11)}{shortcut}"])


def lip_join(lines: list[str]) -> str:
    return "\n".join(lines)


def split_multiline_cell(left: str, right: str, left_width: int, right_width: int) -> list[str]:
    left_lines = left.splitlines()
    right_lines = right.splitlines()
    height = max(len(left_lines), len(right_lines))
    rows = []
    for index in range(height):
        lvalue = left_lines[index] if index < len(left_lines) else ""
        rvalue = right_lines[index] if index < len(right_lines) else ""
        rows.append(f"{ansi_cell(lvalue, left_width)}  {ansi_cell(rvalue, right_width)}")
    return rows


def capture_panel(title_text: str, body: list[str], width: int, mark: str = "▪", tag: str = "") -> str:
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        draw_panel(title_text, body, width, mark, tag)
    return output.getvalue().rstrip("\n")


def key_item(key: str, name: str, detail: str, width: int, max_detail_lines: int = 2) -> str:
    keycap = f"{ORANGE}{BOLD}\033[48;5;52m {key} {RESET}"
    title_line = f"{keycap}  {styled(name, AMBER, bold=True)}"
    detail_lines = textwrap.wrap(detail, max(8, width - 6))[:max_detail_lines]
    return "\n".join([title_line, *[styled("     " + line, MUTED) for line in detail_lines]])


def hero_box(title_text: str, body: list[str], width: int, tag: str = "", mark: str = "") -> list[str]:
    width = max(24, width)
    inner = width - 2
    rows = [f"{ORANGE}┌{'─' * (width - 2)}┐{RESET}"]
    title_prefix = f" {mark} " if mark else " "
    title_value = styled(title_prefix + title_text.upper(), ORANGE, bold=True)
    tag_value = badge(tag) if tag else ""
    header = title_value
    if tag_value:
        header = ansi_cell(title_value, max(1, inner - visible_len(tag_value) - 1)) + " " + tag_value
    rows.append(f"{ORANGE}│{RESET}{ansi_cell(header, inner)}{ORANGE}│{RESET}")
    for line in body:
        rows.append(f"{ORANGE}│{RESET} {ansi_cell(line, inner - 1)}{ORANGE}│{RESET}")
    rows.append(f"{ORANGE}└{'─' * (width - 2)}┘{RESET}")
    return rows


def hero_section(title_text: str, body: list[str], width: int, tag: str = "", mark: str = "") -> list[str]:
    width = max(24, width)
    inner = width - 2
    title_prefix = f"{mark} " if mark else ""
    title_value = styled(title_prefix + title_text.upper(), ORANGE, bold=True)
    tag_value = badge(tag) if tag else ""
    header = title_value
    if tag_value:
        header = ansi_cell(title_value, max(1, inner - visible_len(tag_value) - 2)) + "  " + tag_value
    rows = [ansi_cell(header, width)]
    rows.extend(" " + ansi_cell(line, inner - 1) for line in body)
    return rows


def render_columns(left: list[str], right: list[str], left_width: int, right_width: int) -> list[str]:
    height = max(len(left), len(right))
    rows = []
    for index in range(height):
        left_value = left[index] if index < len(left) else ""
        right_value = right[index] if index < len(right) else ""
        rows.append(f"{ansi_cell(left_value, left_width)}  {ansi_cell(right_value, right_width)}")
    return rows


def queue_item_lines(action: dict[str, Any], index: int, width: int, active: bool, compact: bool) -> list[str]:
    body_width = max(24, width)
    marker = styled("▌", ORANGE, bold=True) if active else " "
    number = styled(str(index + 1), AMBER, bold=True)
    group = badge(str(action["group"]))
    key = styled(f"[{action['key']}]", ORANGE, bold=True)
    title_prefix = f"{marker} {number}  "
    title_width = max(10, body_width - visible_len(title_prefix) - visible_len(group) - 1)
    detail_prefix = "     NEXT: "
    detail_width = max(8, body_width - visible_len(detail_prefix) - visible_len(key) - 2)
    title = styled(clip_text(str(action["title"]), title_width), TEXT if active else WHITE, bold=active)
    detail = styled(clip_text(str(action["detail"]), detail_width), TEXT if active else WHITE)
    lines = [
        f"{title_prefix}{ansi_cell(title, title_width)} {group}",
        f"{detail_prefix}{ansi_cell(detail, detail_width)}  {key}",
    ]
    if not compact:
        lines.append(styled(" " + "─" * max(8, body_width - 2), MUTED, dim=True))
    return lines


def load_quick_actions() -> list[dict[str, Any]]:
    def normalize(item: dict[str, Any], fallback: int) -> dict[str, Any] | None:
        command = item.get("command")
        if command is None:
            normalized = []
        elif isinstance(command, str):
            normalized = [piece for piece in shlex.split(command) if piece]
        elif isinstance(command, list):
            normalized = [str(piece) for piece in command if str(piece).strip()]
        else:
            return None
        dry_run = item.get("dry_run_command") if item.get("dry_run_command") is not None else normalized
        if isinstance(dry_run, str):
            dry_run = [piece for piece in shlex.split(dry_run) if piece]
        if not isinstance(dry_run, list):
            return None
        return {
            "key": str(item.get("key") or str(fallback)),
            "label": str(item.get("label") or item.get("name") or f"Action {fallback}"),
            "id": str(item.get("id") or f"action-{fallback}"),
            "description": str(item.get("description") or ""),
            "allowlist": [str(value).lower() for value in (item.get("allowlist") or [])],
            "command": [str(piece) for piece in normalized],
            "dry_run_command": [str(piece) for piece in dry_run],
            "target_node": str(item.get("target_node") or "cluster"),
            "availability_check": str(item.get("availability_check") or "always"),
            "expected_output_signal": str(item.get("expected_output_signal") or ""),
        }

    payload: Any
    if ACTION_FIXTURE:
        try:
            payload = json.loads(Path(ACTION_FIXTURE).read_text(encoding="utf-8"))
        except Exception:
            payload = []
    else:
        try:
            payload = json.loads(ACTION_REGISTRY.read_text(encoding="utf-8"))
        except Exception:
            payload = []
    actions: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        payload = payload.get("actions") or []
    if isinstance(payload, list):
        for index, item in enumerate(payload, 1):
            if not isinstance(item, dict):
                continue
            action = normalize(item, index)
            if action is not None:
                actions.append(action)
    return actions


def action_cluster_payload() -> tuple[dict[str, Any], str | None]:
    if CLUSTER_FIXTURE:
        try:
            payload = json.loads(Path(CLUSTER_FIXTURE).read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload, None
            return {}, "cluster fixture must be a JSON object"
        except Exception as exc:
            return {}, str(exc)
    try:
        return cluster_snapshot(), None
    except Exception as exc:
        return {}, str(exc)


def action_command_text(command: Any) -> str:
    if isinstance(command, list):
        return " ".join(str(piece) for piece in command)
    return str(command or "")


def action_command_is_safe(command: Any) -> tuple[bool, str]:
    if not isinstance(command, list):
        return False, "invalid command"
    if not command:
        return False, "no command configured"
    first = str(command[0]).strip()
    if not first:
        return False, "no command configured"
    if first in UNSAFE_ACTION_COMMANDS:
        return False, f"unsafe shell wrapper blocked: {first}"
    if first in SAFE_ACTION_COMMANDS or first.startswith("./scripts/"):
        return True, ""
    return False, f"unsafe command blocked: {first}"


def cluster_panel_payload() -> tuple[dict[str, Any], str | None]:
    if CLUSTER_FIXTURE:
        try:
            payload = json.loads(Path(CLUSTER_FIXTURE).read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload, None
            return {}, "cluster fixture must be a JSON object"
        except Exception as exc:
            return {}, str(exc)
    try:
        return cluster_snapshot(), None
    except Exception as exc:
        return {}, str(exc)


def action_is_allowed(action: dict[str, Any], platform_name: str) -> tuple[bool, str]:
    platform_name = normalize_platform_name(platform_name)
    allowlist = [str(value).lower() for value in action.get("allowlist") or []]
    if not allowlist:
        return True, ""
    if platform_name not in allowlist:
        return False, f"not available on {platform_name} (allowlist: {', '.join(allowlist)})"
    return True, ""


def action_cluster_available(action: dict[str, Any], cluster_payload: dict[str, Any], cluster_error: str | None) -> tuple[bool, str]:
    if cluster_error:
        return False, f"cluster payload unavailable: {cluster_error}"
    policy = str(action.get("availability_check") or "always")
    if policy == "always":
        return True, ""
    health = cluster_payload.get("health") or {}
    nodes = health.get("nodes") or []
    if policy == "non_empty_cluster":
        if not nodes:
            return False, "cluster has no registered nodes"
        return True, ""
    if policy == "degraded_nodes":
        if not nodes:
            return False, "cluster has no registered nodes"
        if any(str(item.get("state") or "") in {"degraded", "offline"} for item in nodes):
            return True, ""
        return False, "no degraded or offline nodes"
    return True, ""


def build_action_rows(
    cluster_payload: dict[str, Any],
    cluster_error: str | None = None,
    platform_name: str = ACTION_PLATFORM,
) -> list[dict[str, Any]]:
    platform_name = normalize_platform_name(platform_name)
    rows: list[dict[str, Any]] = []
    for action in load_quick_actions():
        entry = dict(action)
        available, reason = action_is_allowed(action, platform_name)
        if available:
            cluster_available, cluster_reason = action_cluster_available(action, cluster_payload, cluster_error)
            if not cluster_available:
                available = False
                reason = cluster_reason
        if available:
            safe, safety_reason = action_command_is_safe(action.get("command"))
            if not safe:
                available = False
                reason = safety_reason
        if not reason:
            reason = "ready"
        entry.update(
            {
                "available": available,
                "availability_reason": reason,
            }
        )
        rows.append(entry)
    return rows


def action_metadata_lines(action: dict[str, Any], width: int = 58) -> list[str]:
    allowlist = ", ".join(action.get("allowlist") or []) or "all"
    lines = [
        f"DESCRIPTION  {clip_text(str(action.get('description') or 'n/a'), max(1, width - 14))}",
        f"ALLOWLIST    {clip_text(allowlist, max(1, width - 14))}",
        f"TARGET NODE  {clip_text(str(action.get('target_node') or 'cluster'), max(1, width - 14))}",
        f"DRY RUN      {clip_text(' '.join(action.get('dry_run_command') or []), max(1, width - 14))}",
        f"EXPECTED     {clip_text(str(action.get('expected_output_signal') or 'n/a'), max(1, width - 14))}",
        f"CHECK       {clip_text(str(action.get('availability_check') or 'always'), max(1, width - 14))}",
    ]
    return lines


def normalize_action_result(status: str, action: dict[str, Any], elapsed_seconds: float, returncode: int | None, output: str) -> dict[str, Any]:
    command_text = action_command_text(action.get("command"))
    output_lines = [line for line in (output or "").splitlines() if line]
    if not output_lines and returncode is not None:
        output_lines = [f"exit {returncode}"]
    if not output_lines:
        output_lines = ["completed"]
    return {
        "label": action.get("label", "") or "action",
        "command": command_text,
        "status": status,
        "returncode": returncode,
        "elapsed_seconds": round(elapsed_seconds, 2),
        "output": output_lines[:8],
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }


def execute_action(action: dict[str, Any], timeout: float = 12.0) -> dict[str, Any]:
    command = action.get("command")
    if not command:
        return normalize_action_result("empty", action, 0.0, 0, "No command configured")
    if not isinstance(command, list):
        return normalize_action_result("blocked", action, 0.0, 126, f"invalid command: {command}")

    safe, reason = action_command_is_safe(command)
    if not safe:
        return normalize_action_result("blocked", action, 0.0, 126, reason)

    started = time.time()
    try:
        result = subprocess.run(
            command,
            cwd=ROOT_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        return normalize_action_result("unavailable", action, time.time() - started, None, f"unavailable: {exc}")
    except Exception as exc:
        return normalize_action_result("failed", action, time.time() - started, None, str(exc))
    output = (result.stdout or "").strip()
    status = "succeeded" if result.returncode == 0 else "failed"
    return normalize_action_result(status, action, time.time() - started, result.returncode, output)


def action_status_label(status: str) -> str:
    if status == "succeeded":
        return f"{GREEN}SUCCEEDED{RESET}"
    if status == "failed":
        return f"{ORANGE}FAILED{RESET}"
    if status == "blocked":
        return f"{AMBER}BLOCKED{RESET}"
    if status == "running":
        return f"{AMBER}RUNNING{RESET}"
    if status == "idle":
        return f"{MUTED}IDLE{RESET}"
    if status == "unavailable":
        return f"{ORANGE}UNAVAILABLE{RESET}"
    if status == "empty":
        return f"{MUTED}EMPTY{RESET}"
    return f"{ORANGE}DEGRADED{RESET}"


def run_action(action: dict[str, Any], *, dry_run: bool = False) -> list[str]:
    command = action.get("dry_run_command" if dry_run else "command") or action.get("command") or []
    runnable = dict(action)
    runnable["command"] = command
    result = execute_action(runnable)
    command_text = action_command_text(runnable.get("command"))
    lines = [f"{result['status'].upper()}: {command_text}", *result["output"][:8]]
    signal = str(action.get("expected_output_signal") or "").strip()
    if signal and result["status"] == "succeeded":
        matched = any(signal in str(line) for line in result.get("output") or [])
        if not matched:
            lines.append(f"expected output signal missing: {signal}")
    return lines


def idle_action_result(action: dict[str, Any]) -> dict[str, Any]:
    return {
        "label": action.get("label", "") or "action",
        "command": " ".join(action.get("command") or []),
        "status": "idle",
        "returncode": None,
        "elapsed_seconds": None,
        "output": ["No action has run yet."],
        "updated_at": "never run",
    }


def action_output_lines(status: dict[str, Any], width: int = 58) -> list[str]:
    lines = [
        styled(f"{action_status_label(str(status.get('status') or 'degraded'))} {status.get('label', 'action')}", TEXT),
        styled(str(status.get('updated_at') or 'no time'), MUTED),
    ]
    for line in status.get("output") or []:
        if len(lines) >= 5:
            break
        lines.append(styled(clip_text(str(line), width), TEXT))
    if status.get("elapsed_seconds") is not None:
        lines.append(styled(f"elapsed {status['elapsed_seconds']}s", MUTED))
    return lines


def run_action_async(action_id: str, action: dict[str, Any]) -> None:
    def worker() -> None:
        result = execute_action(action)
        with ACTIONS_STATE_LOCK:
            if ACTIONS_STATE.get("running") == action_id:
                ACTIONS_STATE["running"] = None
            results = dict(ACTIONS_STATE.get("results") or {})
            results[action_id] = result
            ACTIONS_STATE["results"] = results
            ACTIONS_STATE["message"] = f"{result['status']} ({result.get('label')})"
            ACTIONS_STATE["output"] = [line for line in (result.get("output") or [])[:8]]

    if not action_id:
        return
    with ACTIONS_STATE_LOCK:
        if ACTIONS_STATE.get("running") is not None:
            ACTIONS_STATE["message"] = "blocked: action already running"
            return
        ACTIONS_STATE["running"] = action_id
        ACTIONS_STATE["message"] = f"running: {str(action.get('label') or 'action')}"
        ACTIONS_STATE["output"] = ["running ..."]
    threading.Thread(target=worker, daemon=True).start()


def hero_context_lines() -> list[str]:
    try:
        data = metrics()
        resource = f"CPU {data['cpu']}%  RAM {data['ram']}%  DISK {data['disk']}%  TEMP {data['temp']}C"
    except Exception:
        resource = "metrics unavailable"
    events = event_lines(3)
    rows = [
        styled("CONTEXT ENGINE", AMBER, bold=True),
        styled(resource, TEXT),
        styled("RECENT SIGNALS", AMBER, bold=True),
    ]
    if not events:
        rows.append(styled("no recent events", MUTED))
    for _, stamp, label, age in events:
        rows.append(f"{styled(stamp, MUTED)}  {styled(clip_text(label, 44), TEXT)}  {styled(age, MUTED)}")
    return rows


def handle_hero_key(state: dict[str, Any], key: str) -> bool:
    if not key:
        return True
    state["last_key"] = key.replace("\x1b", "esc")
    selected = int(state.get("selected", 0))
    if key in {"q", "Q", "\x03"}:
        return False
    if key in {"j", "J", "\x1b[B"}:
        state["selected"] = min(len(HERO_QUEUE) - 1, selected + 1)
        state["message"] = "selection moved"
        return True
    if key in {"k", "K", "\x1b[A"}:
        state["selected"] = max(0, selected - 1)
        state["message"] = "selection moved"
        return True
    if key in {"1", "2", "3", "4", "5"}:
        state["selected"] = min(len(HERO_QUEUE) - 1, int(key) - 1)
        state["message"] = "selection moved"
        return True
    if key in {"r", "R"}:
        state["message"] = "refreshed"
        state["output"] = ["state rebuilt from jobs, logs, and local metrics"]
        return True
    if key in {"o", "O"}:
        state["message"] = "context opened"
        state["output"] = [strip_ansi(line) for line in hero_context_lines()]
        return True
    if key in {"u", "U"}:
        state["message"] = "update drafted"
        state["output"] = [
            "EOD update",
            "Central action pane is now readable and keyboard-driven.",
            "Volcano background remains in place.",
            "Next: attach project-specific commands to each action.",
        ]
        return True
    if key in {"a", "A", "\r", "\n"}:
        action = HERO_QUEUE[int(state.get("selected", 0))]
        state["message"] = "running " + action["title"]
        state["output"] = run_action(action)
        return True
    if key == "?":
        state["message"] = "palette"
        state["output"] = [
            "j/k or arrows: move",
            "1-5: direct select",
            "a/enter: run selected",
            "o: context",
            "u: draft update",
            "r: refresh",
            "q: quit pane",
        ]
        return True
    return True


def handle_actions_key(state: dict[str, Any], key: str) -> bool:
    if not key:
        return True
    cluster_payload, cluster_error = action_cluster_payload()
    actions = build_action_rows(cluster_payload, cluster_error)
    max_index = len(actions) - 1
    if max_index < 0:
        state["selected"] = 0
    else:
        state["selected"] = max(0, min(max_index, int(state.get("selected", 0))))
    state["last_key"] = key.replace("\x1b", "esc")
    selected = int(state.get("selected", 0))
    if key in {"q", "Q", "\x03"}:
        return False
    if key in {"j", "J", "\x1b[B", "down"}:
        state["selected"] = min(max_index, selected + 1)
        state["message"] = "selection moved"
        return True
    if key in {"k", "K", "\x1b[A", "up"}:
        state["selected"] = max(0, selected - 1)
        state["message"] = "selection moved"
        return True
    if key in {"1", "2", "3", "4", "5", "6", "7", "8", "9"}:
        number = int(key)
        state["selected"] = min(max_index, max(0, number - 1))
        state["message"] = "selection moved"
        return True
    if key in {"r", "R"}:
        state["message"] = "refreshed"
        state["output"] = ["state rebuilt from jobs, logs, and local metrics"]
        return True
    if key in {"\r", "\n", "a", "A"}:
        if max_index < 0:
            state["message"] = "no actions available"
            state["output"] = ["No configured actions to run."]
            return True
        if state.get("running") is not None:
            state["message"] = "action in progress"
            state["output"] = ["Wait for selected action to finish."]
            return True
        action = actions[state["selected"]]
        if not action.get("available"):
            state["message"] = f"{action.get('label', 'action')} unavailable"
            state["output"] = [str(action.get("availability_reason") or "action unavailable")]
            return True
        if not action.get("command"):
            state["message"] = f"{action.get('label', 'action')} skipped"
            state["output"] = ["No command configured."]
            return True
        state["message"] = f"launching: {action.get('label', 'action')}"
        run_action_async(str(action.get("id") or ""), action)
        return True
    if key in {"d", "D"}:
        if max_index < 0:
            state["message"] = "no actions available"
            state["output"] = ["No configured actions to dry-run."]
            return True
        action = actions[state["selected"]]
        if not action.get("available"):
            state["message"] = f"{action.get('label', 'action')} unavailable"
            state["output"] = [str(action.get("availability_reason") or "action unavailable")]
            return True
        dry_run_command = action.get("dry_run_command") or action.get("command") or []
        safe, reason = action_command_is_safe(dry_run_command)
        if not safe:
            state["message"] = f"{action.get('label', 'action')} blocked"
            state["output"] = [reason]
            return True
        state["message"] = f"dry-running: {action.get('label', 'action')}"
        state["output"] = run_action(action, dry_run=True)
        return True
    if key == "?":
        state["message"] = "palette"
        state["output"] = [
            "j/k or arrows: move",
            "1-9: direct select",
            "enter/a: run selected",
            "d: dry-run selected",
            "r: refresh",
            "q: quit pane",
        ]
        return True
    return True


def handle_jobs_key(state: dict[str, Any], key: str) -> bool:
    if not key:
        return True
    try:
        payload = load_jobs()
        jobs = payload.get("jobs", [])
    except Exception:
        jobs = []
    max_index = len(jobs) - 1
    if max_index < 0:
        state["selected"] = 0
    else:
        state["selected"] = max(0, min(max_index, int(state.get("selected", 0))))
    state["last_key"] = key.replace("\x1b", "esc")
    selected = int(state.get("selected", 0))
    if key in {"q", "Q", "\x03"}:
        return False
    if key in {"j", "J", "\x1b[B", "down"}:
        state["selected"] = min(max_index, selected + 1)
        state["message"] = "selection moved"
        return True
    if key in {"k", "K", "\x1b[A", "up"}:
        state["selected"] = max(0, selected - 1)
        state["message"] = "selection moved"
        return True
    if key in {"1", "2", "3", "4", "5", "6", "7", "8", "9"}:
        number = int(key)
        state["selected"] = min(max_index, max(0, number - 1))
        state["message"] = "selection moved"
        return True
    if key in {"r", "R"}:
        state["message"] = "refreshed"
        state["output"] = ["state rebuilt from jobs, logs, and local metrics"]
        return True
    if key == "?":
        state["message"] = "palette"
        state["output"] = [
            "j/k or arrows: move",
            "1-9: direct select",
            "r: refresh",
            "q: quit pane",
        ]
        return True
    return True


def read_key(timeout: float) -> str:
    ready, _, _ = select.select([sys.stdin], [], [], timeout)
    if not ready:
        return ""
    key = sys.stdin.read(1)
    if key == "\x1b":
        time.sleep(0.01)
        while select.select([sys.stdin], [], [], 0)[0]:
            key += sys.stdin.read(1)
    return key


def run_text(cmd: list[str], timeout: int = 4) -> str:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except Exception:
        return ""
    return (result.stdout or result.stderr).strip()


def strip_ansi(value: str) -> str:
    result = ""
    i = 0
    while i < len(value):
        if value[i] == "\033":
            i += 1
            while i < len(value) and value[i] != "m":
                i += 1
        else:
            result += value[i]
        i += 1
    return result


def char_width(char: str) -> int:
    if not char:
        return 0
    codepoint = ord(char)
    if codepoint == 0 or codepoint < 32 or 0x7F <= codepoint < 0xA0:
        return 0
    if unicodedata.combining(char):
        return 0
    if 0xFE00 <= codepoint <= 0xFE0F:
        return 0
    if unicodedata.east_asian_width(char) in {"F", "W"}:
        return 2
    return 1


def visible_len(value: str) -> int:
    return sum(char_width(char) for char in strip_ansi(value))


def pad_visible(value: str, width: int) -> str:
    return value + " " * max(0, width - visible_len(value))


def clip_text(value: str, width: int) -> str:
    plain = strip_ansi(str(value))
    if visible_len(plain) <= width:
        return plain
    if width <= 3:
        return "." * max(0, width)
    target = max(0, width - 3)
    clipped = []
    used = 0
    for char in plain:
        char_cells = char_width(char)
        if used + char_cells > target:
            break
        clipped.append(char)
        used += char_cells
    return "".join(clipped) + "..."


def render_ansi_image(path: Path, max_columns: int, max_lines: int) -> bool:
    try:
        from PIL import Image
    except Exception:
        return False
    try:
        image = Image.open(path).convert("RGB")
    except Exception:
        return False
    if image.width <= 0 or image.height <= 0:
        return False

    columns = max(16, min(max_columns, 110))
    max_pixel_height = max(8, max_lines * 2)
    scale = min(columns / image.width, max_pixel_height / image.height)
    width = max(1, round(image.width * scale))
    height = max(2, round(image.height * scale))
    if height % 2:
        height -= 1
    image = image.resize((width, height))

    left_pad = " " * max(0, (max_columns - width) // 2)
    pixels = image.load()
    for y in range(0, height, 2):
        row = [left_pad]
        for x in range(width):
            top = pixels[x, y]
            bottom = pixels[x, min(y + 1, height - 1)]
            row.append(
                f"\033[38;2;{top[0]};{top[1]};{top[2]}m"
                f"\033[48;2;{bottom[0]};{bottom[1]};{bottom[2]}m"
                f"{UPPER_HALF_BLOCK}"
            )
        row.append(RESET)
        print("".join(row))
    return True


def parse_node_states(status_output: str) -> dict[str, str]:
    states: dict[str, str] = {}
    in_nodes = False
    for line in status_output.splitlines():
        stripped = strip_ansi(line).strip()
        if stripped == "nodes":
            in_nodes = True
            continue
        if not in_nodes:
            continue
        if not stripped:
            continue
        parts = stripped.split()
        if len(parts) >= 2:
            states[parts[0]] = parts[1]
    return states


def clean_event_label(source: str, line: str) -> str:
    plain = strip_ansi(line)
    if 'GET /api/jobs ' in plain:
        return "jobs-dashboard completed"
    if 'GET /api/network ' in plain:
        return "cluster health check ok"
    if 'GET /api/state ' in plain:
        return "system state refreshed"
    if "Industrial workspace" in plain and "composed" in plain:
        return "workspace composed"
    if "Applied Kitty theme:" in plain:
        return "kitty theme applied"
    if plain.startswith("dashboard: running"):
        return "dashboard started"
    if "Completed successfully" in plain:
        return f"{source} completed"
    if not plain:
        return source
    if "] " in plain:
        plain = plain.split("] ", 1)[1]
    return plain


def event_lines(limit: int = 5) -> list[tuple[str, str, str, str]]:
    events: list[tuple[float, str, str, str, str]] = []
    if not LOG_ROOT.exists():
        return []
    for path in LOG_ROOT.glob("*/*.log"):
        try:
            stat = path.stat()
            last = ""
            for raw in reversed(path.read_text(errors="replace").splitlines()):
                if raw.strip() and "Log file:" not in raw and "Log saved to:" not in raw:
                    last = raw.strip()
                    break
            age = max(1, int(time.time() - stat.st_mtime))
            if age < 60:
                age_text = f"{age}s"
            elif age < 3600:
                age_text = f"{age // 60}m"
            else:
                age_text = f"{age // 3600}h"
            label = clean_event_label(path.parent.name, last).replace("_", "-")
            events.append((stat.st_mtime, datetime.fromtimestamp(stat.st_mtime).strftime("%H:%M"), label, age_text, path.parent.name))
        except OSError:
            continue
    events.sort(reverse=True)
    rows = []
    seen: set[str] = set()
    for _, stamp, label, age_text, source in events:
        if label in seen:
            continue
        seen.add(label)
        level = "hot" if source in {"cluster-jobs", "dashboard", "industrial-os", "industrial-workspace"} else "quiet"
        rows.append((level, stamp, label, age_text))
        if len(rows) >= limit:
            break
    return rows


def load_recent_activity(
    limit: int = 12,
    *,
    sources: list[str] | None = None,
    severities: list[str] | None = None,
    query: str = "",
) -> list[dict[str, Any]]:
    return load_recent_activity_filtered(limit=limit, sources=sources, severities=severities, query=query)


def load_agent_work_detail_payload(root_dir: Path, issue_id: int, timeout: int = 8) -> dict[str, Any]:
    command = ["python3", str(root_dir / "scripts" / "agent_work.py"), "show", str(issue_id), "--json"]
    try:
        result = subprocess.run(command, cwd=root_dir, capture_output=True, text=True, timeout=timeout, check=False)
    except Exception:
        return {}
    if result.returncode != 0:
        return {}
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def agent_work_journal_events(
    root_dir: Path,
    agent_payload: dict[str, Any] | None,
    *,
    detail_payloads: dict[str, Any] | None = None,
    now: float | None = None,
    limit: int = 12,
) -> list[dict[str, Any]]:
    if not agent_payload:
        return []
    issues = [issue for issue in (agent_payload.get("issues") or []) if isinstance(issue, dict)]
    if not issues:
        return []
    rows: list[dict[str, Any]] = []
    max_issues = min(len(issues), max(1, int(limit or 12)))
    for issue in issues[:max_issues]:
        issue_id = issue.get("id")
        if issue_id is None:
            continue
        detail: dict[str, Any] | None = None
        if detail_payloads is not None:
            detail = detail_payloads.get(str(issue_id))
            if not isinstance(detail, dict):
                try:
                    detail = detail_payloads.get(int(issue_id))  # type: ignore[arg-type]
                except Exception:
                    detail = None
            if not isinstance(detail, dict):
                continue
        else:
            detail = load_agent_work_detail_payload(root_dir, int(issue_id))
        if not detail:
            continue
        journals = detail.get("journals") or []
        if not isinstance(journals, list):
            continue
        journal = next((item for item in journals if isinstance(item, dict) and str(item.get("notes") or "").strip()), None)
        if not journal:
            continue
        note = str(journal.get("notes") or "").strip()
        created_on = parse_timestamp(journal.get("created_on") or issue.get("updated_on") or now or time.time())
        issue_status = str(issue.get("status") or detail.get("status") or "unknown").strip()
        subject = str(issue.get("subject") or detail.get("subject") or "agent work").strip()
        rows.append(
            event(
                source="redmine",
                kind="journal",
                message=f"#{issue_id} {note}",
                timestamp=created_on,
                severity=classify_severity("redmine", note, issue_status),
                fingerprint=f"redmine:journal:{issue_id}:{journal.get('id') or note}",
                metadata={
                    "issue_id": issue_id,
                    "journal_id": journal.get("id"),
                    "author": journal.get("author") or "",
                    "status": issue_status,
                    "subject": subject,
                    "note": note,
                },
                now=now,
            )
        )
    return rows


def load_recent_activity_filtered(
    *,
    limit: int = 12,
    sources: list[str] | None = None,
    severities: list[str] | None = None,
    query: str = "",
) -> list[dict[str, Any]]:
    fetch_limit = max(int(limit or 12) * 4, 50)
    if ACTIVITY_FIXTURE:
        try:
            fixture_path = Path(ACTIVITY_FIXTURE)
            fixture_payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        except Exception:
            fixture_payload = None
        if isinstance(fixture_payload, dict):
            log_root_value = fixture_payload.get("log_root") or "logs"
            log_root = Path(str(log_root_value))
            if not log_root.is_absolute():
                log_root = (fixture_path.parent / log_root).resolve()

            def coerce_payload(key: str) -> dict[str, Any] | None:
                value = fixture_payload.get(key)
                return value if isinstance(value, dict) else None

            fixture_limit = fixture_payload.get("limit")
            fixture_now = fixture_payload.get("now")
            detail_payloads = fixture_payload.get("issue_detail_payloads")
            rows = build_activity_events(
                log_root=log_root,
                cluster_payload=coerce_payload("cluster_payload"),
                jobs_payload=coerce_payload("jobs_payload"),
                agent_payload=coerce_payload("agent_payload"),
                limit=max(int(fixture_limit) if str(fixture_limit or "").strip() else limit, fetch_limit),
                now=float(fixture_now) if str(fixture_now or "").strip() else None,
                include_placeholders=bool(fixture_payload.get("include_placeholders", True)),
            )
            rows.extend(
                agent_work_journal_events(
                    ROOT_DIR,
                    coerce_payload("agent_payload"),
                    detail_payloads=detail_payloads if isinstance(detail_payloads, dict) else None,
                    now=float(fixture_now) if str(fixture_now or "").strip() else None,
                    limit=fetch_limit,
                )
            )
            rows = dedupe_sort_events(rows, fetch_limit)
            return filter_activity_events(rows, sources=sources, severities=severities, query=query)[:limit]
    cluster_payload: dict[str, Any] | None = None
    jobs_payload: dict[str, Any] | None = None
    agent_payload: dict[str, Any] | None = None
    try:
        cluster_payload = cluster_snapshot()
    except Exception:
        cluster_payload = None
    try:
        jobs_payload = load_jobs()
    except Exception:
        jobs_payload = None
    try:
        agent_payload = load_agent_work_payload(ROOT_DIR)
    except Exception:
        agent_payload = None
    rows = build_activity_events(
        log_root=LOG_ROOT,
        cluster_payload=cluster_payload,
        jobs_payload=jobs_payload,
        agent_payload=agent_payload,
        limit=fetch_limit,
    )
    rows.extend(
        agent_work_journal_events(
            ROOT_DIR,
            agent_payload,
            now=None,
            limit=fetch_limit,
        )
    )
    rows = dedupe_sort_events(rows, fetch_limit)
    return filter_activity_events(rows, sources=sources, severities=severities, query=query)[:limit]


def activity_severity_label(severity: str) -> str:
    severity = str(severity or "info").strip().lower() or "info"
    if severity == "critical":
        return styled("CRIT", ORANGE, bold=True)
    if severity == "warning":
        return styled("WARN", AMBER, bold=True)
    if severity == "ok":
        return styled("OK", GREEN, bold=True)
    return styled("INFO", BLUE, bold=True)


def activity_sources_label(item: dict[str, Any]) -> str:
    sources = [str(value).strip() for value in (item.get("sources") or [item.get("source") or ""]) if str(value).strip()]
    if not sources:
        return "unknown"
    if len(sources) == 1:
        return sources[0]
    if len(sources) == 2:
        return f"{sources[0]} + {sources[1]}"
    return f"{sources[0]} + {sources[1]} +{len(sources) - 2}"


def activity_filter_summary(sources: list[str], severities: list[str], query: str) -> str:
    parts: list[str] = []
    if sources:
        parts.append("source=" + ", ".join(sources))
    if severities:
        parts.append("severity=" + ", ".join(severities))
    if query.strip():
        parts.append("query=" + query.strip())
    return " | ".join(parts) if parts else "all events"


def activity_row(item: dict[str, Any], width: int) -> str:
    age = styled(f"{str(item.get('age') or ''):>5}", MUTED)
    severity = activity_severity_label(str(item.get("severity") or "info"))
    source_width = max(6, min(36, width // 3))
    sources = styled(clip_text(activity_sources_label(item), source_width), WHITE, bold=True)
    fixed_width = 12 + visible_len(sources)
    message_width = max(1, width - fixed_width)
    message = styled(clip_text(str(item.get("message") or ""), message_width), WHITE)
    return f"{age} {severity} {sources} {message}"


def render_hero() -> None:
    columns, lines = term_size()
    compact = lines < 56
    very_compact = lines < 44
    width = max(64, min(columns - 2, 120))
    content = width - 4
    now = datetime.now().strftime("%H:%M:%S")
    try:
        payload = load_jobs()
        jobs = payload.get("jobs", [])
    except Exception:
        jobs = []
    active_jobs = sum(
        1
        for job in jobs
        if str(job.get("status") or "").lower() not in {"succeeded", "failed", "done", "completed"}
    )
    active_jobs = active_jobs or min(7, max(1, len(jobs)))
    selected = int(HERO_STATE.get("selected", 0))
    selected_action = HERO_QUEUE[selected]

    top_left = styled(f"{now}  hero", MUTED)
    top_right = styled(f"JOBS {active_jobs} ACTIVE  •  ACTIONS {HERO_READY_ACTIONS} READY", AMBER, bold=True)
    print(ansi_cell(top_left, content - visible_len(top_right) - 1) + " " + top_right)
    brand = styled("> INDUSTRIAL OPS v1.1.0", ORANGE, bold=True)
    print(brand)
    print(f"{ORANGE}{'─' * width}{RESET}")
    headline = styled("MISSION CONTROL // CENTRAL ACTION PANE", AMBER, bold=True)
    subtitle = styled("not a dashboard - an action router for the whole cockpit", WHITE)
    print(headline)
    print(subtitle)
    print()

    mission_body: list[str] = []
    mission_body.extend(mission_row("OBJECTIVE", "Ship central pane that turns intent → task → action.", content - 2))
    mission_body.extend(mission_row("NEXT ACTION", "Wire selected queue item to an executable command.", content - 2, GREEN))
    if not compact:
        mission_body.extend(mission_row("PROJECT", "Cento Industrial Cockpit / Bubble Tea TUI", content - 2))
        mission_body.extend(mission_row("DEADLINE", "Today 18:00  •  demo-ready by EOD", content - 2, AMBER))
        mission_body.extend(mission_row("SUCCESS", "3 real keybinds, 1 screenshot, 1 follow-up narrative.", content - 2))
        mission_body.extend(mission_row("WHY NOW", "Make the cockpit useful for 100+ engineers, not just pretty.", content - 2))
        mission_body.append("")
    mission_body.append(badge("CONFIDENCE 72%") + styled("  •  RISK: pane looks cool but does not reduce clicks", TEXT))
    print("\n".join(hero_section("MISSION BRIEF", mission_body, width, "LIVE", "▫")))
    print()

    side_by_side = width >= 84
    left_width = round((width - 2) * 0.58) if side_by_side else width
    right_width = width - left_width - 2 if side_by_side else width
    left_body_width = max(24, left_width - 5)
    queue_lines: list[str] = []
    for index, action in enumerate(HERO_QUEUE):
        item_lines = queue_item_lines(action, index, left_body_width, index == selected, compact)
        if index == len(HERO_QUEUE) - 1 and not compact:
            item_lines = item_lines[:-1]
        queue_lines.extend(item_lines)

    context_lines = [
        styled("CHANGE RADAR", AMBER, bold=True),
        styled("2 files changed since last green", TEXT),
        styled("ANTI-STALL", AMBER, bold=True),
        styled("same failed cmd seen 3x", TEXT),
        styled("BLAST RADIUS", AMBER, bold=True),
        styled("cluster pane + docs + PR linked", TEXT),
        styled("BLOCKER WATCH", AMBER, bold=True),
        styled("no owner on docs review", TEXT),
        styled("SESSION HEAT", ORANGE, bold=True),
        styled("▂▃▂▃▄▃▄▅▄▆▅▇▆", ORANGE, bold=True),
    ]
    if not compact:
        context_lines[6:6] = [
            styled("NARRATIVE", AMBER, bold=True),
            styled("demo update can be generated", TEXT),
        ]

    queue_box = hero_box("ACTIVE WORK QUEUE", queue_lines, left_width, "SELECTABLE", "▦")
    detail_box = hero_box("CONTEXT ENGINE", context_lines, right_width, "HOT", "⚡")
    if side_by_side:
        for row in render_columns(queue_box, detail_box, left_width, right_width):
            print(row)
    else:
        print("\n".join(queue_box))
        print()
        print("\n".join(detail_box))
    print()

    col_width = max(20, (width - 10) // 3)
    hub_items = [
        ("j", "JOBS", "focus job queue + show last exit code"),
        ("c", "CLUSTER", "jump to cluster health / owners / blast radius"),
        ("a", "ACT", "run selected next action"),
        ("r", "REFRESH", "rebuild state from jobs, git, TODOs"),
        ("o", "OPEN", "launch context pack: docs, PR, logs"),
        ("n", "CAPTURE", "turn current line / clipboard into a task"),
        ("b", "BLOCK", "file blocker + draft owner ask"),
        ("u", "UPDATE", "generate EOD / demo follow-up from session"),
        ("?", "PALETTE", "type any cockpit command"),
    ]
    hub_lines: list[str] = []
    for row_start in range(0, len(hub_items), 3):
        row = hub_items[row_start:row_start + 3]
        titles = []
        details = []
        for key, label, detail in row:
            titles.append(ansi_cell(f"{badge(key)}  {styled(label, AMBER, bold=True)}", col_width))
            if not very_compact:
                details.append(ansi_cell(styled("   " + clip_text(detail, col_width - 4), WHITE), col_width))
        hub_lines.append("  ".join(titles))
        if details:
            hub_lines.append("  ".join(details))
        if row_start < 6 and not compact:
            hub_lines.append("")
    print("\n".join(hero_box("KEYBOARD / ACTION HUB", hub_lines, width, "GLOBAL", "⌘")))
    selected_line = styled("SELECTED › " + selected_action["title"], AMBER, bold=True)
    action_line = styled(f"ACTION › {HERO_STATE.get('message', 'ready')} | press [a] run [o] context [u] update", TEXT)
    selected_width = min(content, visible_len(selected_line) + 2)
    print()
    print(f"{ORANGE}{'─' * width}{RESET}")
    print(f"{ansi_cell(selected_line, selected_width)}{ansi_cell(action_line, max(10, width - selected_width))}")


def render_jobs() -> None:
    title("Jobs Dashboard")
    try:
        payload = load_jobs()
        jobs = payload.get("jobs", [])
    except Exception as exc:
        print(f"{ORANGE}jobs unavailable:{RESET} {exc}")
        return
    counts = payload.get("counts") or {}
    states = payload.get("states") or {}
    state = str(payload.get("state") or ("empty" if not jobs else "ok"))
    state_color = GREEN if state == "ok" else (AMBER if state == "empty" else ORANGE)
    count_order = ["running", "queued", "planned", "dry-run", "succeeded", "failed", "invalid", "unknown"]
    count_parts = [f"{key.upper()} {counts[key]}" for key in count_order if counts.get(key)]
    print(
        f"{TEXT}TOTAL{RESET} {len(jobs):>4}   "
        + "   ".join(count_parts)
        + f"   {state_color}{state.upper()}{RESET}"
    )
    if states:
        print(f"{MUTED}states:{RESET} " + " ".join(f"{key}={value}" for key, value in sorted(states.items())))
    print()
    if not jobs:
        print(f"{MUTED}No cluster jobs found. Run `cento cluster-job ...` to create one.{RESET}")
        return
    columns, lines = term_size()
    max_rows = min(len(jobs), max(3, min(6, lines - 18)))
    selected = max(0, min(len(jobs) - 1, int(JOBS_STATE.get("selected", 0))))
    JOBS_STATE["selected"] = selected
    start = max(0, min(selected - max_rows // 2, max(0, len(jobs) - max_rows)))
    visible_jobs = jobs[start:start + max_rows]
    header = (
        f"{MUTED}{'ID':<22}{RESET} "
        f"{MUTED}{'STATUS':<10}{RESET} "
        f"{MUTED}{'TSK':>3}{RESET} "
        f"{MUTED}{'RES':>3}{RESET} "
        f"{MUTED}{'FAIL':>4}{RESET} "
        f"{MUTED}{'AGE':>5}{RESET} "
        f"{MUTED}{'STATE':<8}{RESET} "
        f"{MUTED}STEP / FEATURE{RESET}"
    )
    print(header)
    for offset, job in enumerate(visible_jobs):
        index = start + offset
        summary = job.get("job_summary") or {}
        status = str(summary.get("status") or job.get("status") or "")
        row_state = str(summary.get("state") or "")
        state_color = ORANGE if row_state == "degraded" else (MUTED if row_state == "empty" else GREEN)
        task_count = summary.get("task_count", len(job.get("tasks", [])))
        result_count = summary.get("result_count", len(job.get("results", [])))
        failed_count = summary.get("failed_task_count", 0)
        age = str(summary.get("updated_age") or job.get("updated_age") or "")
        step = str(summary.get("current_step") or job.get("feature") or "")
        feature = str(summary.get("feature") or job.get("feature") or "")
        label = f"{step} · {feature}" if feature and feature != step else step or feature
        print(
            f"{('▌' if index == selected else ' ')}{ORANGE}{str(job.get('id', ''))[:21]:<21}{RESET} "
            f"{status:<10} "
            f"{TEXT}{int(task_count):>3}{RESET} "
            f"{TEXT}{int(result_count):>3}{RESET} "
            f"{AMBER}{int(failed_count):>4}{RESET} "
            f"{MUTED}{age:>5}{RESET} "
            f"{state_color}{row_state:<8}{RESET} "
            f"{clip_text(label, 50)}"
        )
        reasons = summary.get("degraded_reasons") or []
        if reasons:
            print(f"{MUTED}{'':<22}   degraded: {clip_text('; '.join(map(str, reasons)), 62)}{RESET}")
    print()
    selected_job = jobs[selected]
    detail_width = max(24, min(columns - 2, 96))
    detail_body = job_detail_lines(selected_job, detail_width - 4)
    print("\n".join(hero_box("SELECTED JOB", detail_body, detail_width, "DETAIL", "▸")))


def job_last_exit(job: dict[str, Any]) -> str:
    tasks = [task for task in job.get("tasks", []) if isinstance(task, dict)]
    for task in reversed(tasks):
        returncode = task.get("returncode")
        if returncode is not None:
            return str(returncode)
    summary = job.get("job_summary") or {}
    status = str(summary.get("status") or job.get("status") or "").lower()
    if status in {"running", "planned", "queued", "dry-run"}:
        return "pending"
    return "n/a"


def job_next_action(job: dict[str, Any]) -> str:
    summary = job.get("job_summary") or {}
    status = str(summary.get("status") or job.get("status") or "unknown").lower()
    state = str(summary.get("state") or "")
    latest_log = summary.get("latest_log") or {}
    if state == "degraded" or status in {"failed", "error", "invalid"}:
        if latest_log.get("exists"):
            return "inspect latest log, then rerun or mark blocked with failure detail"
        return "inspect job.json and task manifests; log path is missing"
    if status == "running":
        return "tail latest log and wait for task result or timeout"
    if status in {"planned", "queued"}:
        return "run the job or keep planned until an operator assigns execution"
    if status == "dry-run":
        return "review generated scripts/manifests before actual execution"
    return "review summary artifact and archive outcome"


def job_detail_lines(job: dict[str, Any], width: int) -> list[str]:
    summary = job.get("job_summary") or {}
    tasks = [task for task in job.get("tasks", []) if isinstance(task, dict)]
    latest_log = summary.get("latest_log") or {}
    reasons = summary.get("degraded_reasons") or []
    summary_path = str(job.get("summary") or "n/a")
    summary_exists = bool(summary.get("summary_exists"))
    command = str(job.get("agent_command") or "n/a")
    feature = str(summary.get("feature") or job.get("feature") or "n/a")
    status = str(summary.get("status") or job.get("status") or "unknown").upper()
    state = str(summary.get("state") or "unknown").upper()
    result_count = int(summary.get("result_count") or 0)
    failed_count = int(summary.get("failed_task_count") or 0)
    lines = [
        styled(f"ID         {clip_text(str(job.get('id') or 'n/a'), width - 11)}", TEXT),
        styled(f"STATUS     {status}", TEXT),
        styled(f"STATE      {state}", TEXT),
        styled(f"AGE        {clip_text(str(summary.get('updated_age') or job.get('updated_age') or 'n/a'), width - 11)}", TEXT),
        styled(f"FEATURE    {clip_text(feature, width - 11)}", TEXT),
        styled(f"RESULTS    {result_count} total / {failed_count} failed", TEXT),
        styled(f"SUMMARY    {'present' if summary_exists else 'missing'}", GREEN if summary_exists else AMBER),
        styled(f"SUMMARY    {clip_text(summary_path, width - 11)}", TEXT),
        styled(f"COMMAND    {clip_text(command, width - 11)}", TEXT),
        styled(f"LAST EXIT  {clip_text(job_last_exit(job), width - 11)}", TEXT),
    ]
    if reasons:
        lines.append(styled(f"REASONS    {clip_text('; '.join(map(str, reasons)), width - 11)}", AMBER))
    lines.append(styled("TASK STATE", ORANGE, bold=True))
    if not tasks:
        lines.append(styled("  no tasks recorded", MUTED))
    else:
        for task in tasks[:4]:
            result = task.get("returncode")
            task_state = "pending" if result is None else ("ok" if str(result) == "0" else f"exit {result}")
            log_state = "present" if task.get("log_exists") else "missing"
            script_state = "present" if task.get("script_exists") else "missing"
            manifest_state = "present" if task.get("manifest_exists") else "missing"
            task_line = (
                f"  {clip_text(str(task.get('id') or ''), 14):<14} "
                f"{clip_text(str(task.get('node') or ''), 8):<8} "
                f"{clip_text(task_state, 9):<9} "
                f"log={log_state:<7} "
                f"script={script_state:<7} "
                f"manifest={manifest_state:<7} "
                f"{clip_text(str(task.get('title') or ''), max(8, width - 67))}"
            )
            lines.append(styled(task_line, TEXT))
    lines.append(styled("LATEST LOG", ORANGE, bold=True))
    if latest_log.get("path"):
        lines.append(styled(f"  {'present' if latest_log.get('exists') else 'missing'}", GREEN if latest_log.get("exists") else AMBER))
        lines.append(styled(clip_text(str(latest_log.get("path")), width), MUTED))
        for line in (latest_log.get("tail") or [])[:4]:
            lines.append(styled(clip_text(str(line), width), TEXT))
    else:
        lines.append(styled("  missing", AMBER))
    lines.append(styled("NEXT", ORANGE, bold=True))
    lines.append(styled(clip_text(job_next_action(job), width), WHITE))
    return lines


def _cluster_node_mesh_label(node: Any) -> str:
    if node["is_local"]:
        return "local"
    if node["socket_path"]:
        if node["state"] == "degraded" and any("stale mesh socket" in reason for reason in node.get("reasons", [])):
            return "stale"
        return "sock" if node["socket_present"] else "no-sock"
    return "none"


def _cluster_resource_lines(model: dict[str, Any], width: int) -> list[str]:
    resource_health = model.get("resource_health") or {}
    if not isinstance(resource_health, dict):
        return []
    lines: list[str] = []
    local = resource_health.get("local") or {}
    if isinstance(local, dict):
        problem = str(local.get("problem") or "").strip()
        metrics = local.get("metrics") or {}
        if problem:
            lines.append(styled(f"local metrics unavailable: {clip_text(problem, max(12, width - 28))}", AMBER))
        elif isinstance(metrics, dict) and metrics:
            bits: list[str] = []
            for key, label, suffix in (
                ("cpu", "CPU", "%"),
                ("ram", "RAM", "%"),
                ("disk", "DISK", "%"),
                ("temp", "TEMP", "C"),
                ("net_down", "DOWN", "/s"),
                ("net_up", "UP", "/s"),
            ):
                value = metrics.get(key)
                if value in (None, ""):
                    continue
                bits.append(f"{label}={value}{suffix}")
            if bits:
                lines.append(styled(f"local {' '.join(bits)}", WHITE))
    remote = resource_health.get("remote") or {}
    if isinstance(remote, dict):
        remote_nodes = remote.get("nodes") or []
        if remote_nodes:
            summary: list[str] = []
            for item in remote_nodes:
                node_id = str(item.get("id") or "")
                state = str(item.get("state") or "")
                status = str(item.get("status") or "")
                if state == "online":
                    summary.append(f"{node_id}: {status or 'telemetry missing'}")
                else:
                    summary.append(f"{node_id}: {state}")
            lines.append(styled(f"remote {clip_text('; '.join(summary), max(20, width - 10))}", MUTED))
        else:
            summary = str(remote.get("summary") or "").strip()
            if summary:
                lines.append(styled(clip_text(summary, width), MUTED))
    return lines


def _cluster_event_lines(events: list[dict[str, Any]], width: int) -> list[str]:
    if not events:
        return [styled("no recent cluster events", MUTED)]
    lines: list[str] = []
    for event in events[:4]:
        severity = str(event.get("severity") or "info").lower()
        dot = MUTED
        if severity in {"critical", "warning"}:
            dot = AMBER
        elif severity == "ok":
            dot = GREEN
        stamp = str(event.get("stamp") or "")
        age = str(event.get("age") or "")
        message = clip_text(str(event.get("message") or ""), max(12, width - 18))
        lines.append(f" {styled('●', dot)}  {styled(stamp, MUTED)}  {styled(message, WHITE)} {styled(age, MUTED)}")
    return lines


def render_cluster() -> None:
    try:
        payload, error = cluster_panel_payload()
        if error:
            raise RuntimeError(error)
    except Exception as exc:
        print(f"{ORANGE}{BOLD}▣ CLUSTER STATUS{RESET}\n")
        print(f"{ORANGE}cluster unavailable:{RESET} {exc}")
        return
    model = build_cluster_panel_model(payload)

    table_rows: list[tuple[str, str, str, str, str]] = []
    for node in model["nodes"][:6]:
        m = node["metrics"]
        cpu = f"{m.get('cpu')}%" if m.get("cpu") is not None else "--"
        mem = f"{m.get('ram')}%" if m.get("ram") is not None else "--"
        table_rows.append((
            clip_text(node["id"], 16),
            node["state"],
            cpu,
            mem,
            _cluster_node_mesh_label(node),
        ))

    overall = model["overall"]
    total = len(model["nodes"])
    online_count = model["counts"].get("online", 0)

    if overall == "unavailable":
        health_label, health_color = "UNAVAILABLE", ORANGE
    elif overall == "healthy":
        health_label, health_color = "HEALTHY", GREEN
    elif overall == "empty":
        health_label, health_color = "EMPTY", AMBER
    else:
        health_label, health_color = "DEGRADED", AMBER

    print(f"{ORANGE}{BOLD}▣ CLUSTER STATUS{RESET}")
    print()
    title_line = f"{ORANGE}{BOLD}CENTO-CLUSTER{RESET}"
    health_badge = f"{health_color}{BOLD}{health_label}{RESET}"
    print(f"{pad_visible(title_line, PANEL_WIDTH - 13)}{AMBER}{DIM}[{RESET} {health_badge} {AMBER}{DIM}]{RESET}")
    print(f"{WHITE}{BOLD}{online_count}/{total} nodes online{RESET}")
    counts = model["counts"]
    if counts:
        print(f"{MUTED}online={counts.get('online', 0)} degraded={counts.get('degraded', 0)} offline={counts.get('offline', 0)}{RESET}")
    if model["relay_present"]:
        print(f"{MUTED}relay={clip_text(model['relay_host'], 28)}{RESET}")
    else:
        print(f"{AMBER}relay=missing{RESET}")
    if not model["status_ok"]:
        print(f"{AMBER}cluster status command unavailable{RESET}")
    if not model["mesh_ok"] and any(n["socket_path"] for n in model["nodes"]):
        print(f"{AMBER}bridge mesh-status unavailable{RESET}")
    metrics_error = ""
    metrics_payload = payload.get("metrics")
    if isinstance(metrics_payload, dict):
        metrics_error = str(metrics_payload.get("error") or "").strip()
    if metrics_error:
        print(f"{AMBER}metrics unavailable: {clip_text(metrics_error, PANEL_WIDTH - 22)}{RESET}")
    print()
    print(f"{MUTED}+{'-' * (PANEL_WIDTH - 2)}+{RESET}")
    print(
        f"{MUTED}|{RESET} "
        f"{BLUE}{BOLD}{'NODE':<16}{RESET}  "
        f"{BLUE}{BOLD}{'STATUS':<11}{RESET} "
        f"{BLUE}{BOLD}{'CPU':>5}{RESET} "
        f"{BLUE}{BOLD}{'MEM':>5}{RESET} "
        f"{BLUE}{BOLD}{'MESH':>8}{RESET} "
        f"{MUTED}|{RESET}"
    )
    print(f"{MUTED}|{'-' * (PANEL_WIDTH - 2)}|{RESET}")
    for label, state, cpu, mem, mesh_label in table_rows:
        dot_color = GREEN if state == "online" else (AMBER if state == "degraded" else MUTED)
        state_text = f"{dot_color}●{RESET} {state}"
        print(
            f"{MUTED}|{RESET} "
            f"{WHITE}{label:<16}{RESET}  "
            f"{pad_visible(state_text, 11)} "
            f"{AMBER}{cpu:>5}{RESET} "
            f"{AMBER}{mem:>5}{RESET} "
            f"{WHITE}{mesh_label:>8}{RESET} "
            f"{MUTED}|{RESET}"
        )
    if not table_rows:
        print(f"{MUTED}|{RESET} {WHITE}{'no nodes registered':<{PANEL_WIDTH - 4}}{RESET} {MUTED}|{RESET}")
    print(f"{MUTED}+{'-' * (PANEL_WIDTH - 2)}+{RESET}")

    resource_lines = _cluster_resource_lines(model, PANEL_WIDTH)
    print()
    print(f"{ORANGE}{BOLD}RESOURCE HEALTH{RESET}")
    if resource_lines:
        for line in resource_lines[:4]:
            print(f" {line}")
    else:
        print(f" {MUTED}no resource health available{RESET}")

    print()
    print(f"{ORANGE}{BOLD}RECENT CLUSTER EVENTS{RESET}")
    event_lines = _cluster_event_lines(list(model.get("recent_events") or []), PANEL_WIDTH)
    for line in event_lines:
        print(f" {line}")

    if model["degraded_reasons"]:
        print()
        print(f"{ORANGE}{BOLD}DEGRADED REASONS{RESET}")
        for reason in model["degraded_reasons"][:4]:
            print(f" {AMBER}●{RESET} {WHITE}{clip_text(str(reason), PANEL_WIDTH - 5)}{RESET}")
    if model["remediation_actions"]:
        print()
        print(f"{ORANGE}{BOLD}REMEDIATION{RESET}")
        for action in model["remediation_actions"][:4]:
            owner = str(action.get("owner") or "operator")
            act_label = str(action.get("action") or "inspect")
            command = ""
            commands = action.get("commands") or []
            if commands:
                command = str(commands[0])
            line = f"{action.get('node')}: {act_label} · {owner}"
            print(f" {AMBER}▶{RESET} {WHITE}{clip_text(line, PANEL_WIDTH - 5)}{RESET}")
            if command:
                print(f"   {MUTED}{clip_text(command, PANEL_WIDTH - 4)}{RESET}")


def render_resources() -> None:
    title("System Resources")
    data = metrics()
    print(bar("CPU", data["cpu"]))
    print(bar("RAM", data["ram"]))
    print(bar("DISK", data["disk"]))
    print(f"TEMP    {ORANGE}{data['temp']}C{RESET}\n")
    ps = run_text(["ps", "-eo", "pid,pcpu,pmem,comm", "--sort=-pcpu"], timeout=4)
    lines = ps.splitlines()[:9]
    for line in lines:
        print(line)


def render_activity() -> None:
    title("Activity Feed")
    options = dict(ACTIVITY_RENDER_OPTIONS)
    events = load_recent_activity(
        limit=int(options.get("limit") or 14),
        sources=[str(value) for value in options.get("sources") or []],
        severities=[str(value) for value in options.get("severities") or []],
        query=str(options.get("query") or ""),
    )
    columns, _ = term_size()
    if not events:
        summary = activity_filter_summary(
            [str(value) for value in options.get("sources") or []],
            [str(value) for value in options.get("severities") or []],
            str(options.get("query") or ""),
        )
        if summary == "all events":
            print(f"{MUTED}No activity events found.{RESET}")
        else:
            print(f"{MUTED}No activity events matched the active filters ({summary}).{RESET}")
        return
    summary = activity_filter_summary(
        [str(value) for value in options.get("sources") or []],
        [str(value) for value in options.get("severities") or []],
        str(options.get("query") or ""),
    )
    print(f"{MUTED}FILTERS{RESET} {WHITE}{clip_text(summary, 72)}{RESET}")
    print(
        f"{MUTED}{'AGE':>5}{RESET} "
        f"{MUTED}{'SEV':<8}{RESET} "
        f"{MUTED}{'SOURCE':<24}{RESET} "
        f"{MUTED}MESSAGE{RESET}"
    )
    for item in events:
        print(activity_row(item, columns))


def render_actions() -> None:
    title("Quick Actions")
    columns, _ = term_size()
    payload, error = action_cluster_payload()
    rows = build_action_rows(payload, error)
    with ACTIONS_STATE_LOCK:
        action_state = dict(ACTIONS_STATE)
        results = dict(action_state.get("results", {}))
        running = action_state.get("running")
        status_message = action_state.get("message", "ready")
        status_output = [str(line) for line in (action_state.get("output") or [])]
    selected = int(action_state.get("selected", 0))
    selected = max(0, min(len(rows) - 1, selected)) if rows else 0
    with ACTIONS_STATE_LOCK:
        ACTIONS_STATE["selected"] = selected

    print(f"{MUTED}STATUS{RESET}  {status_message}")
    if error:
        print(f"{AMBER}{badge('cluster-unavailable')}{RESET} {styled(f'cluster signal unavailable: {error}', AMBER)}")
    if not rows:
        print(f"{MUTED}No actions configured.{RESET}")
        return

    print(f"{MUTED}{'KEY':<6}{'ACTION':<31}{'STATE':<12}{'AVAILABILITY':<{max(16, columns - 56)}}{RESET}")
    for index, row in enumerate(rows):
        active = index == selected
        command = row.get("command") or []
        command_text = " ".join(command) if isinstance(command, list) else str(command)
        reason = str(row.get("availability_reason") or "")
        action_id = str(row.get("id") or "")
        row_status = results.get(action_id)
        if running == action_id:
            state_label = action_status_label("running")
            reason = "running selected action"
        elif row_status is not None:
            state_label = action_status_label(str(row_status.get("status") or "degraded"))
        elif not bool(row.get("available")):
            state_label = action_status_label("unavailable")
        else:
            state_label = f"{GREEN}READY{RESET}"
        print(
            f"{'▌' if active else ' '} {badge(str(row.get('key') or index + 1))} "
            f"{styled(clip_text(str(row.get('label') or f'Action {index + 1}'), max(1, columns - 52)), WHITE, bold=active)} "
            f"{state_label:<12} "
            f"{MUTED}{clip_text(reason or command_text, max(1, columns - 56))}{RESET}"
        )

    selected_row = rows[selected]
    selected_id = str(selected_row.get("id") or "")
    selected_status = dict(results.get(selected_id) or {})
    if not selected_status:
        selected_status = idle_action_result(selected_row)
    selected_status.setdefault("label", selected_row.get("label", f"Action {selected + 1}"))
    selected_status.setdefault("output", status_output)
    selected_status.setdefault("status", "idle")
    if running == selected_id:
        selected_status["status"] = "running"
        selected_status["output"] = status_output or ["running ..."]
    elif not bool(selected_row.get("available")):
        selected_status["status"] = "unavailable"
        selected_status["output"] = [str(selected_row.get("availability_reason") or "unavailable")]

    print(f"\n{ORANGE}{'ACTION DETAILS':<14}{RESET} {styled(str(selected_row.get('label') or ''), WHITE)}")
    for line in action_metadata_lines(selected_row, width=max(16, columns - 24)):
        print(styled(line, TEXT if line.startswith("DESCRIPTION") else MUTED))
    print(f"\n{ORANGE}{'LAST RESULT':<11}{RESET} {styled(str(selected_row.get('label') or ''), WHITE)}")
    for line in action_output_lines(selected_status, width=max(16, columns - 24)):
        print(line)
    print(f"\n{MUTED}Controls: j/k move, 1-9 select, enter/a run, d dry-run, q quit{RESET}")


RENDERERS = {
    "hero": render_hero,
    "jobs": render_jobs,
    "cluster": render_cluster,
    "resources": render_resources,
    "activity": render_activity,
    "actions": render_actions,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Render Industrial OS terminal panels.")
    parser.add_argument("panel", choices=sorted(RENDERERS))
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--once", action="store_true", help="Render one frame and exit.")
    parser.add_argument("--plain", action="store_true", help="Strip ANSI color from --once output.")
    parser.add_argument("--limit", type=int, default=14, help="Limit activity rows when rendering the feed.")
    parser.add_argument("--source", action="append", default=[], help="Filter activity by source. Repeatable.")
    parser.add_argument("--severity", action="append", default=[], help="Filter activity by severity. Repeatable.")
    parser.add_argument("--query", default="", help="Filter activity by message substring.")
    args = parser.parse_args()

    ACTIVITY_RENDER_OPTIONS.update(
        {
            "limit": max(1, int(args.limit or 14)),
            "sources": [str(value) for value in args.source or [] if str(value).strip()],
            "severities": [str(value) for value in args.severity or [] if str(value).strip()],
            "query": str(args.query or ""),
        }
    )

    if args.once:
        frame = render_frame(args.panel)
        if args.plain:
            frame = strip_ansi(frame)
        print(frame, end="")
        return 0

    def stop(_signum: int, _frame: object) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    enter_live_display()
    old_term = None
    if args.panel in {"hero", "actions", "jobs"} and sys.stdin.isatty():
        old_term = termios.tcgetattr(sys.stdin.fileno())
        tty.setcbreak(sys.stdin.fileno())
    try:
        while True:
            paint_frame(render_frame(args.panel))
            if args.panel in {"hero", "actions", "jobs"} and sys.stdin.isatty():
                key = read_key(args.interval)
                if args.panel == "hero":
                    if not handle_hero_key(HERO_STATE, key):
                        return 0
                elif args.panel == "actions":
                    if not handle_actions_key(ACTIONS_STATE, key):
                        return 0
                else:
                    if not handle_jobs_key(JOBS_STATE, key):
                        return 0
            else:
                time.sleep(args.interval)
    except KeyboardInterrupt:
        return 0
    finally:
        if old_term is not None:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_term)
        leave_live_display()


if __name__ == "__main__":
    raise SystemExit(main())
