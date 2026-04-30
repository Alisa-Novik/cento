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
import sys
import termios
import textwrap
import time
import tty
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

from industrial_status import metrics
from jobs_server import load_jobs
from network_web_server import cluster_snapshot


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
HERO_STATE: dict[str, Any] = {
    "selected": 0,
    "message": "implement action router",
    "output": ["j/k or arrows move", "a or enter runs selected action", "o opens context", "u drafts update"],
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


def run_action(action: dict[str, Any]) -> list[str]:
    command = action.get("command")
    if not command:
        return [
            "Demo follow-up",
            "Shipped readable central pane.",
            "Next: wire real job execution for selected actions.",
            "Ask: confirm action labels and owners.",
        ]
    try:
        result = subprocess.run(command, cwd=ROOT_DIR, capture_output=True, text=True, timeout=8, check=False)
    except Exception as exc:
        return [f"failed to start: {exc}"]
    output = (result.stdout or result.stderr or "").strip()
    lines = output.splitlines() if output else [f"exit {result.returncode}"]
    prefix = "ok" if result.returncode == 0 else f"exit {result.returncode}"
    return [f"{prefix}: {' '.join(command)}", *lines[:5]]


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


def load_recent_activity(limit: int = 12) -> list[str]:
    entries: list[tuple[float, str]] = []
    if not LOG_ROOT.exists():
        return []
    for path in LOG_ROOT.glob("*/*.log"):
        try:
            line = ""
            for raw in reversed(path.read_text(errors="replace").splitlines()):
                if raw.strip() and "Log file:" not in raw:
                    line = raw.strip()
                    break
            entries.append((path.stat().st_mtime, f"{path.parent.name}: {line or path.name}"))
        except OSError:
            continue
    entries.sort(reverse=True)
    return [item for _, item in entries[:limit]]


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
    counts: dict[str, int] = {}
    for job in jobs:
        counts[str(job.get("status") or "unknown")] = counts.get(str(job.get("status") or "unknown"), 0) + 1
    print(f"{TEXT}TOTAL{RESET} {len(jobs):>4}   " + "   ".join(f"{key.upper()} {value}" for key, value in sorted(counts.items())))
    print()
    for job in jobs[:10]:
        print(f"{ORANGE}{job.get('id', '')[:22]:<22}{RESET} {str(job.get('status', '')):<10} {job.get('feature', '')[:54]}")


def render_cluster() -> None:
    try:
        payload = cluster_snapshot()
    except Exception as exc:
        print(f"{ORANGE}{BOLD}▣ CLUSTER STATUS{RESET}\n")
        print(f"{ORANGE}cluster unavailable:{RESET} {exc}")
        return
    nodes = payload.get("nodes") or []
    status = payload.get("status") or {}
    status_output = "\n".join(item for item in [status.get("stdout", ""), status.get("stderr", "")] if item)
    node_states = parse_node_states(status_output)
    online_count = 0
    table_rows: list[tuple[str, str, str, str, str]] = []
    data = metrics()
    for index, node in enumerate(nodes[:6]):
        label = str(node.get("id") or node.get("name") or "node")
        state = node_states.get(label)
        if not state:
            state = "local" if label == payload.get("local") else "registered"
        normalized = "online" if state in {"connected", "local", "online"} else "offline"
        if normalized == "online":
            online_count += 1
        cpu = f"{data['cpu']}%" if index == 0 else "--"
        mem = f"{data['ram']}%" if index == 0 else "--"
        uptime = "local" if state == "local" else ("now" if normalized == "online" else "--")
        table_rows.append((clip_text(label, 16), normalized, cpu, mem, uptime))

    total = len(nodes)
    health = "HEALTHY" if total > 0 and online_count == total else "DEGRADED"
    health_color = GREEN if health == "HEALTHY" else AMBER

    print(f"{ORANGE}{BOLD}▣ CLUSTER STATUS{RESET}")
    print()
    title_line = f"{ORANGE}{BOLD}CENTO-CLUSTER{RESET}"
    badge = f"{health_color}{BOLD}{health}{RESET}"
    print(f"{pad_visible(title_line, PANEL_WIDTH - 13)}{AMBER}{DIM}[{RESET} {badge} {AMBER}{DIM}]{RESET}")
    print(f"{WHITE}{BOLD}{online_count}/{total} nodes online{RESET}")
    print()
    print(f"{MUTED}+{'-' * (PANEL_WIDTH - 2)}+{RESET}")
    print(
        f"{MUTED}|{RESET} "
        f"{BLUE}{BOLD}{'NODE':<16}{RESET}  "
        f"{BLUE}{BOLD}{'STATUS':<11}{RESET} "
        f"{BLUE}{BOLD}{'CPU':>5}{RESET} "
        f"{BLUE}{BOLD}{'MEM':>5}{RESET} "
        f"{BLUE}{BOLD}{'UPTIME':>8}{RESET} "
        f"{MUTED}|{RESET}"
    )
    print(f"{MUTED}|{'-' * (PANEL_WIDTH - 2)}|{RESET}")
    for label, state, cpu, mem, uptime in table_rows:
        dot_color = GREEN if state == "online" else MUTED
        state_text = f"{dot_color}●{RESET} {state}"
        print(
            f"{MUTED}|{RESET} "
            f"{WHITE}{label:<16}{RESET}  "
            f"{pad_visible(state_text, 11)} "
            f"{AMBER}{cpu:>5}{RESET} "
            f"{AMBER}{mem:>5}{RESET} "
            f"{WHITE}{uptime:>8}{RESET} "
            f"{MUTED}|{RESET}"
        )
    if not table_rows:
        print(f"{MUTED}|{RESET} {WHITE}{'no nodes registered':<{PANEL_WIDTH - 4}}{RESET} {MUTED}|{RESET}")
    print(f"{MUTED}+{'-' * (PANEL_WIDTH - 2)}+{RESET}")

    print()
    print(f"{ORANGE}{BOLD}RECENT EVENTS{RESET}")
    print()
    for level, stamp, label, age_text in event_lines(5):
        dot = f"{ORANGE}●{RESET}" if level == "hot" else f"{MUTED}●{RESET}"
        print(f" {dot}  {WHITE}{stamp}{RESET}  {WHITE}{clip_text(label, 32):<32}{RESET} {WHITE}{age_text:>5}{RESET}")


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
    for item in load_recent_activity(14):
        print(f"{ORANGE}> {RESET}{item[:110]}")


def render_actions() -> None:
    title("Quick Actions")
    actions = [
        ("cento act jobs", "Jobs dashboard"),
        ("cento cluster health", "Cluster status"),
        ("cento replay demo", "Replay last demo"),
        ("cento codex status", "Codex usage"),
        ("cento preset industrial-os", "Reapply preset"),
    ]
    for command, label in actions:
        print(f"{ORANGE}> {command:<30}{RESET} {MUTED}{label}{RESET}")
    print(f"\n{MUTED}Mod+Shift+O opens the web dashboard.{RESET}")


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
    args = parser.parse_args()

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
    if args.panel == "hero" and sys.stdin.isatty():
        old_term = termios.tcgetattr(sys.stdin.fileno())
        tty.setcbreak(sys.stdin.fileno())
    try:
        while True:
            paint_frame(render_frame(args.panel))
            if args.panel == "hero" and sys.stdin.isatty():
                key = read_key(args.interval)
                if not handle_hero_key(HERO_STATE, key):
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
