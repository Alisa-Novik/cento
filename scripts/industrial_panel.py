#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import time
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
MUTED = "\033[38;5;95m"
TEXT = "\033[38;5;230m"
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
BLUE = "\033[38;5;109m"
WHITE = "\033[38;5;248m"
PANEL_WIDTH = 58
UPPER_HALF_BLOCK = "\u2580"


def term_size() -> tuple[int, int]:
    size = shutil.get_terminal_size((96, 28))
    return size.columns, size.lines


def clear() -> None:
    print("\033[2J\033[H", end="")


def title(text: str) -> None:
    print(f"{ORANGE}{BOLD}> {text.upper()}{RESET}")
    print(f"{MUTED}{'-' * min(term_size()[0], 96)}{RESET}")


def bar(label: str, value: int, width: int = 26) -> str:
    value = max(0, min(100, value))
    filled = round(width * value / 100)
    return f"{label:<7} {ORANGE}{'#' * filled}{MUTED}{'.' * (width - filled)}{RESET} {value:>3}%"


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


def visible_len(value: str) -> int:
    return len(strip_ansi(value))


def pad_visible(value: str, width: int) -> str:
    return value + " " * max(0, width - visible_len(value))


def clip_text(value: str, width: int) -> str:
    plain = strip_ansi(str(value))
    if len(plain) <= width:
        return plain
    return plain[: max(0, width - 1)] + "..."


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
    title("Industrial OS v1.0.0")
    print(f"{AMBER}ENGINEERING MODE{RESET}\n")
    columns, lines = term_size()
    if not HERO_HAS_KITTY_BACKGROUND:
        hero_art = HERO_ART if HERO_ART.exists() else WALLPAPER
        image_lines = max(8, lines - 10)
        if hero_art.exists():
            render_ansi_image(hero_art, columns, image_lines)
    else:
        print("\n" * max(2, lines - 14))
    data = metrics()
    print(bar("CPU", data["cpu"]))
    print(bar("RAM", data["ram"]))
    print(bar("DISK", data["disk"]))
    print(f"TEMP    {ORANGE}{data['temp']}C{RESET}")
    print(f"NET     {ORANGE}{data['net_down']} down / {data['net_up']} up{RESET}")


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
    args = parser.parse_args()
    while True:
        if args.panel == "cluster":
            frame = io.StringIO()
            with contextlib.redirect_stdout(frame):
                print(f"{MUTED}{datetime.now().strftime('%H:%M:%S')}  {args.panel}{RESET}")
                RENDERERS[args.panel]()
            clear()
            print(frame.getvalue(), end="")
        else:
            clear()
            print(f"{MUTED}{datetime.now().strftime('%H:%M:%S')}  {args.panel}{RESET}")
            RENDERERS[args.panel]()
        sys.stdout.flush()
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
