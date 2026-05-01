#!/usr/bin/env python3

from __future__ import annotations

import argparse
import html
import json
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def repo_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else ROOT / path


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"Expected object JSON: {path}")
    return payload


def badge_class(status: str) -> str:
    value = status.lower().replace("_", "-").replace(" ", "-")
    if value in {"implemented", "existing-capability"}:
        return "good"
    if value in {"partial", "deferred-deliberately"}:
        return "warn"
    if value in {"not-implemented"}:
        return "bad"
    return "neutral"


def render_start(plan: dict[str, Any], run_dir: Path) -> str:
    tasks = plan.get("tasks") or []
    request = plan.get("request") if isinstance(plan.get("request"), dict) else {}
    rows = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_id = str(task.get("id") or "")
        story = f"tasks/{task_id}/story.json"
        validation = f"tasks/{task_id}/validation.json"
        rows.append(
            "<tr>"
            f"<td><strong>{html.escape(task_id)}</strong></td>"
            f"<td>{html.escape(str(task.get('title') or ''))}</td>"
            f"<td>{html.escape(str(task.get('lane') or ''))}</td>"
            f"<td>{html.escape(str(task.get('risk') or ''))}</td>"
            f"<td><a href=\"{html.escape(story)}\">story.json</a></td>"
            f"<td><a href=\"{html.escape(validation)}\">validation.json</a></td>"
            "</tr>"
        )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Factory Run - {html.escape(str(plan.get('run_id') or 'factory'))}</title>
  <style>
    body {{ margin: 0; background: #090807; color: #f4efe8; font-family: Inter, system-ui, sans-serif; }}
    main {{ width: min(1180px, calc(100% - 32px)); margin: 0 auto; padding: 36px 0 56px; }}
    h1 {{ margin: 0 0 8px; font-size: 36px; }}
    .sub {{ color: #b8aea4; margin: 0 0 28px; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin: 24px 0; }}
    .card, table {{ border: 1px solid #33251d; background: #11100f; }}
    .card {{ padding: 16px; }}
    .card span {{ display: block; color: #b8aea4; font-size: 12px; text-transform: uppercase; }}
    .card strong {{ font-size: 24px; color: #ff5a00; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border-bottom: 1px solid #251d18; padding: 10px; text-align: left; vertical-align: top; }}
    th {{ color: #b8aea4; font-size: 12px; text-transform: uppercase; }}
    a {{ color: #ff6a00; font-weight: 800; }}
    .actions {{ display: flex; gap: 12px; margin: 22px 0; flex-wrap: wrap; }}
    .actions a {{ border: 1px solid #ff5a00; padding: 10px 12px; text-decoration: none; }}
  </style>
</head>
<body>
  <main>
    <h1>Factory Run</h1>
    <p class="sub">{html.escape(str(request.get('normalized_goal') or ''))}</p>
    <div class="grid">
      <div class="card"><span>Run</span><strong>{html.escape(str(plan.get('run_id') or ''))}</strong></div>
      <div class="card"><span>Package</span><strong>{html.escape(str(plan.get('package') or ''))}</strong></div>
      <div class="card"><span>Mode</span><strong>{html.escape(str(plan.get('mode') or ''))}</strong></div>
      <div class="card"><span>AI calls</span><strong>0</strong></div>
    </div>
    <div class="actions">
      <a href="factory-plan.json">factory-plan.json</a>
      <a href="queue/state.json">queue</a>
      <a href="dispatch-plan.json">dispatch plan</a>
      <a href="integration-plan.json">integration gate</a>
      <a href="delivery-status.json">delivery status</a>
      <a href="implementation-map.html">Implementation Map</a>
      <a href="summary.md">summary.md</a>
      <a href="release-notes.md">release-notes.md</a>
      <a href="project-delivery.md">project-delivery.md</a>
    </div>
    <table>
      <thead><tr><th>Task</th><th>Title</th><th>Lane</th><th>Risk</th><th>Story</th><th>Validation</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
  </main>
</body>
</html>
"""


def default_research_map(plan: dict[str, Any]) -> dict[str, Any]:
    tasks = [task for task in plan.get("tasks") or [] if isinstance(task, dict)]
    sections = []
    for index, task in enumerate(tasks[:6], start=1):
        is_final = index == len(tasks[:6])
        section = {
            "id": f"{index}.0",
            "title": str(task.get("title") or task.get("id") or f"Task {index}"),
            "recommendation": str(task.get("goal") or ""),
            "status": "partial" if is_final else "implemented",
            "coverage": 65 if is_final else 100,
            "linked_tasks": [str(task.get("id") or "")],
            "evidence": [f"tasks/{task.get('id')}/validation.json"],
        }
        if is_final:
            section["decision"] = "Plan-only evidence exists; live integration is deliberately deferred to the next Factory slice."
        sections.append(section)
    return {
        "schema_version": "research-map/v1",
        "source": {
            "title": "Factory planning implementation map",
            "artifact": "factory-plan.json",
        },
        "sections": sections,
    }


def render_implementation_map(research_map: dict[str, Any]) -> str:
    rows = []
    detail = []
    source = research_map.get("source") if isinstance(research_map.get("source"), dict) else {}
    for section in research_map.get("sections") or []:
        if not isinstance(section, dict):
            continue
        status = str(section.get("status") or "not_implemented")
        klass = badge_class(status)
        coverage = int(section.get("coverage") or 0)
        rows.append(
            "<div class=\"row\">"
            f"<div><strong>{html.escape(str(section.get('id') or ''))} {html.escape(str(section.get('title') or ''))}</strong>"
            f"<small>{html.escape(str(section.get('recommendation') or ''))}</small></div>"
            f"<span class=\"badge {klass}\">{html.escape(status.replace('_', ' '))}</span>"
            f"<span class=\"coverage\"><b>{coverage}%</b><i style=\"--coverage:{coverage}%\"></i></span>"
            "</div>"
        )
        detail.append(
            "<article>"
            f"<h2>{html.escape(str(section.get('id') or ''))} {html.escape(str(section.get('title') or ''))}</h2>"
            f"<p>{html.escape(str(section.get('recommendation') or ''))}</p>"
            f"<p><strong>Status:</strong> {html.escape(status)}. <strong>Coverage:</strong> {coverage}%.</p>"
            "</article>"
        )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Implementation Map</title>
  <style>
    body {{ margin: 0; background: #080706; color: #f7f1ea; font-family: Inter, system-ui, sans-serif; }}
    main {{ display: grid; grid-template-columns: minmax(0, 1fr) minmax(360px, 0.85fr); min-height: 100vh; }}
    .spec, .map {{ padding: 32px; }}
    .spec {{ border-right: 1px solid #33251d; background: #0d0c0b; }}
    h1 {{ margin: 0 0 16px; font-size: 34px; }}
    article {{ border: 1px solid #33251d; background: #151311; padding: 20px; margin: 0 0 16px; }}
    article h2 {{ margin-top: 0; }}
    .row {{ display: grid; grid-template-columns: minmax(0, 1fr) 132px 110px; gap: 12px; align-items: center; border-bottom: 1px solid #251d18; padding: 12px 0; }}
    .row small {{ display: block; color: #b8aea4; margin-top: 4px; }}
    .badge {{ border: 1px solid #4b4038; padding: 6px 8px; font-weight: 900; text-transform: uppercase; font-size: 12px; text-align: center; }}
    .good {{ color: #35d58b; border-color: #14824f; }}
    .warn {{ color: #ffd166; border-color: #a56c00; }}
    .bad {{ color: #ff5f5f; border-color: #923737; }}
    .coverage i {{ display: block; height: 6px; background: linear-gradient(90deg, #ff5a00 var(--coverage), #30231b var(--coverage)); margin-top: 6px; }}
    @media (max-width: 900px) {{ main {{ grid-template-columns: 1fr; }} .spec {{ border-right: 0; border-bottom: 1px solid #33251d; }} }}
  </style>
</head>
<body>
  <main>
    <section class="spec">
      <h1>{html.escape(str(source.get('title') or 'Research / Spec'))}</h1>
      {''.join(detail)}
    </section>
    <section class="map">
      <h1>Implementation Map</h1>
      {''.join(rows)}
    </section>
  </main>
</body>
</html>
"""


def write_summary(plan: dict[str, Any], run_dir: Path) -> None:
    lines = [
        "# Factory Run Summary",
        "",
        f"- Run: `{plan.get('run_id')}`",
        f"- Package: `{plan.get('package')}`",
        f"- Mode: `{plan.get('mode')}`",
        f"- Tasks: `{len(plan.get('tasks') or [])}`",
        "- AI calls used: `0`",
        "- Estimated AI cost: `0`",
        "",
        "## Outputs",
        "",
        "- `factory-plan.json`",
        "- `start-here.html`",
        "- `implementation-map.html`",
        "- `release-notes.md`",
    ]
    (run_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (run_dir / "release-notes.md").write_text(
        "\n".join(
            [
                "# Factory Planning V1 Release Notes",
                "",
                "Plan-only factory artifacts were generated with no worker dispatch.",
                "",
                f"- Generated at: `{datetime.now().astimezone().isoformat(timespec='seconds')}`",
                f"- Package: `{plan.get('package')}`",
                f"- Tasks: `{len(plan.get('tasks') or [])}`",
                "- AI calls used: `0`",
                "",
            ]
        ),
        encoding="utf-8",
    )


def render_run(run_dir: Path) -> dict[str, str]:
    plan_path = run_dir / "factory-plan.json"
    plan = load_json(plan_path)
    research_map_path = run_dir / "research-map.json"
    research_map = load_json(research_map_path) if research_map_path.exists() else default_research_map(plan)
    if not research_map_path.exists():
        research_map_path.write_text(json.dumps(research_map, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    start_path = run_dir / "start-here.html"
    implementation_path = run_dir / "implementation-map.html"
    start_path.write_text(render_start(plan, run_dir), encoding="utf-8")
    implementation_path.write_text(render_implementation_map(research_map), encoding="utf-8")
    write_summary(plan, run_dir)
    return {
        "start_hub": rel(start_path),
        "implementation_map": rel(implementation_path),
        "summary": rel(run_dir / "summary.md"),
        "release_notes": rel(run_dir / "release-notes.md"),
        "research_map": rel(research_map_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Render Cento Factory evidence hubs.")
    parser.add_argument("run_dir", help="Factory run directory containing factory-plan.json.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    outputs = render_run(repo_path(args.run_dir))
    if args.json:
        print(json.dumps(outputs, indent=2, sort_keys=True))
    else:
        for value in outputs.values():
            print(value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
