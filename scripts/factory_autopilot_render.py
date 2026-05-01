#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import factory_autopilot_state as ap_state


def _read(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return ap_state.read_json(path)


def render(run_dir: Path) -> dict[str, str]:
    autopilot = ap_state.autopilot_dir(run_dir)
    state = _read(ap_state.state_path(run_dir))
    metrics = _read(ap_state.metrics_path(run_dir))
    stop = _read(ap_state.stop_reason_path(run_dir))
    cycles = sorted((autopilot / "cycles").glob("*/decision.json"))
    actions: list[tuple[str, str, list[str]]] = []
    for decision_path in cycles:
        decision = _read(decision_path)
        actions.append((decision_path.parent.name, str(decision.get("action") or ""), [str(item) for item in decision.get("reasons") or []]))

    lines = [
        "# Factory Autopilot Summary",
        "",
        f"- Run: `{run_dir.name}`",
        f"- Mode: `{(metrics.get('mode') or 'dry_run_control_loop')}`",
        f"- Cycles completed: `{state.get('cycles_completed', 0)}`",
        f"- Last action: `{state.get('last_action', '')}`",
        f"- Stop reason: `{stop.get('reason', 'not_stopped')}`",
        "- AI calls used: 0",
        "- Estimated cost USD: 0",
        "",
        "## Primary Metric",
        "",
        "- `validated integrated output per dollar`",
        f"- Simulated validated integrated progress: `{(metrics.get('progress') or {}).get('validated_integrated', 0)}`",
        "",
        "## Backlogs",
        "",
    ]
    backlogs = (metrics.get("latest_backlogs") or {}) if isinstance(metrics.get("latest_backlogs"), dict) else {}
    for name in ("patch", "validation", "integration", "blocked"):
        lines.append(f"- {name}: `{backlogs.get(name, 0)}`")
    lines.extend(["", "## Cycle Decisions", ""])
    if actions:
        lines.extend(f"- `{cycle}` `{action}`: {', '.join(reasons) if reasons else 'no reason recorded'}" for cycle, action, reasons in actions)
    else:
        lines.append("- No cycles recorded.")
    blocked = (metrics.get("blocked_reasons") or []) if isinstance(metrics.get("blocked_reasons"), list) else []
    lines.extend(["", "## Readiness", ""])
    lines.append(f"- Evidence completeness: `{(metrics.get('evidence') or {}).get('completeness', 'unknown')}`")
    lines.append(f"- Ready for real execution: `{str((metrics.get('readiness') or {}).get('ready_for_real_execution', False)).lower()}`")
    if blocked:
        lines.extend(["", "## Blocked Reasons", "", *[f"- `{item}`" for item in blocked]])
    lines.append("")
    summary = autopilot / "autopilot-summary.md"
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text("\n".join(lines), encoding="utf-8")

    panel = autopilot / "autopilot-panel.html"
    panel.write_text(
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><title>Factory Autopilot</title></head>"
        f"<body><main><h1>Factory Autopilot</h1><p>Run: {run_dir.name}</p>"
        f"<p>Cycles: {state.get('cycles_completed', 0)}</p><p>AI calls used: 0</p>"
        f"<pre>{json.dumps(backlogs, indent=2, sort_keys=True)}</pre></main></body></html>\n",
        encoding="utf-8",
    )
    return {"summary": ap_state.rel(summary), "panel": ap_state.rel(panel)}
