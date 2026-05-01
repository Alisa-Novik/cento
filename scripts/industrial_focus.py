#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from typing import Any


TARGET_CLASSES = {
    "discord",
    "cento-industrial-hero",
    "cento-industrial-terminal",
    "cento-industrial-jobs",
    "cento-industrial-cluster",
    "cento-industrial-agents",
    "cento-industrial-actions",
}

VISUAL_GRAPH = {
    "left": {
        "cento-industrial-hero": "discord",
        "cento-industrial-terminal": "cento-industrial-hero",
        "cento-industrial-cluster": "cento-industrial-jobs",
        "cento-industrial-agents": "cento-industrial-cluster",
        "cento-industrial-actions": "cento-industrial-agents",
    },
    "right": {
        "discord": "cento-industrial-hero",
        "cento-industrial-hero": "cento-industrial-terminal",
        "cento-industrial-jobs": "cento-industrial-cluster",
        "cento-industrial-cluster": "cento-industrial-agents",
        "cento-industrial-agents": "cento-industrial-actions",
    },
    "down": {
        "discord": "cento-industrial-jobs",
        "cento-industrial-hero": "cento-industrial-cluster",
        "cento-industrial-terminal": "cento-industrial-agents",
    },
    "up": {
        "cento-industrial-jobs": "discord",
        "cento-industrial-cluster": "cento-industrial-hero",
        "cento-industrial-agents": "cento-industrial-terminal",
        "cento-industrial-actions": "cento-industrial-terminal",
    },
}


@dataclass(frozen=True)
class Window:
    con_id: int
    klass: str
    rect: dict[str, int]
    focused: bool

    @property
    def cx(self) -> float:
        return self.rect.get("x", 0) + self.rect.get("width", 0) / 2

    @property
    def cy(self) -> float:
        return self.rect.get("y", 0) + self.rect.get("height", 0) / 2


def i3(command: str) -> int:
    return subprocess.run(["i3-msg", command], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False).returncode


def native_focus(direction: str) -> int:
    return i3(f"focus {direction}")


def get_tree() -> dict[str, Any] | None:
    try:
        result = subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True, text=True, check=False, timeout=2)
    except Exception:
        return None
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def workspace_matches(name: str, workspace: str) -> bool:
    return name == workspace or name.startswith(f"{workspace}:")


def find_focused_workspace(node: dict[str, Any], workspace: dict[str, Any] | None = None) -> dict[str, Any] | None:
    if node.get("type") == "workspace":
        workspace = node
    if node.get("focused"):
        return workspace
    for child in node.get("nodes", []) + node.get("floating_nodes", []):
        found = find_focused_workspace(child, workspace)
        if found is not None:
            return found
    return None


def collect_target_windows(node: dict[str, Any]) -> list[Window]:
    windows: list[Window] = []
    props = node.get("window_properties") or {}
    klass = props.get("class", "").lower()
    if node.get("window") is not None and klass in TARGET_CLASSES:
        windows.append(Window(int(node["id"]), klass, node.get("rect") or {}, bool(node.get("focused"))))
    for child in node.get("nodes", []) + node.get("floating_nodes", []):
        windows.extend(collect_target_windows(child))
    return windows


def overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> bool:
    return max(a_start, b_start) < min(a_end, b_end)


def geometry_target(current: Window, windows: list[Window], direction: str) -> Window | None:
    candidates: list[tuple[tuple[float, float, float], Window]] = []
    for candidate in windows:
        if candidate.con_id == current.con_id:
            continue
        crect = candidate.rect
        frect = current.rect
        if direction == "left":
            if candidate.cx >= current.cx:
                continue
            primary = current.cx - candidate.cx
            orth = abs(current.cy - candidate.cy)
            intersects = overlap(frect.get("y", 0), frect.get("y", 0) + frect.get("height", 0), crect.get("y", 0), crect.get("y", 0) + crect.get("height", 0))
        elif direction == "right":
            if candidate.cx <= current.cx:
                continue
            primary = candidate.cx - current.cx
            orth = abs(current.cy - candidate.cy)
            intersects = overlap(frect.get("y", 0), frect.get("y", 0) + frect.get("height", 0), crect.get("y", 0), crect.get("y", 0) + crect.get("height", 0))
        elif direction == "up":
            if candidate.cy >= current.cy:
                continue
            primary = current.cy - candidate.cy
            orth = abs(current.cx - candidate.cx)
            intersects = overlap(frect.get("x", 0), frect.get("x", 0) + frect.get("width", 0), crect.get("x", 0), crect.get("x", 0) + crect.get("width", 0))
        else:
            if candidate.cy <= current.cy:
                continue
            primary = candidate.cy - current.cy
            orth = abs(current.cx - candidate.cx)
            intersects = overlap(frect.get("x", 0), frect.get("x", 0) + frect.get("width", 0), crect.get("x", 0), crect.get("x", 0) + crect.get("width", 0))
        penalty = 0 if intersects else 10_000
        candidates.append(((penalty, orth, primary), candidate))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def industrial_focus(direction: str, workspace: str) -> int:
    tree = get_tree()
    if tree is None:
        return native_focus(direction)
    workspace_node = find_focused_workspace(tree)
    if not workspace_node or not workspace_matches(workspace_node.get("name", ""), workspace):
        return native_focus(direction)

    windows = collect_target_windows(workspace_node)
    by_class = {window.klass: window for window in windows}
    current = next((window for window in windows if window.focused), None)
    if current is None:
        return native_focus(direction)

    graph_target = VISUAL_GRAPH.get(direction, {}).get(current.klass)
    target = by_class.get(graph_target or "") if graph_target else None
    if target is None:
        target = geometry_target(current, windows, direction)
    if target is None:
        return native_focus(direction)
    return i3(f"[con_id={target.con_id}] focus")


def main() -> int:
    parser = argparse.ArgumentParser(description="Focus Industrial OS i3 cockpit panes in visual order.")
    parser.add_argument("direction", choices=["left", "right", "up", "down", "h", "j", "k", "l"])
    parser.add_argument("--workspace", default="1")
    args = parser.parse_args()
    direction = {"h": "left", "j": "down", "k": "up", "l": "right"}.get(args.direction, args.direction)
    return industrial_focus(direction, args.workspace)


if __name__ == "__main__":
    raise SystemExit(main())
