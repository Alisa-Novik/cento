#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN_DIR = ROOT / "workspace" / "runs" / "agent-work" / "no-model-validation-e2e"


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_command(command: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    proc = subprocess.run(command, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    duration_ms = round((time.perf_counter() - started) * 1000, 3)
    return {
        "command": command,
        "cwd": rel(cwd),
        "exit_code": proc.returncode,
        "duration_ms": duration_ms,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def require_ok(result: dict[str, Any]) -> None:
    if result["exit_code"] != 0:
        print(json.dumps(result, indent=2), file=sys.stderr)
        raise SystemExit(result["exit_code"])


def write_fixture_files(run_dir: Path) -> dict[str, Path]:
    fixtures = run_dir / "fixtures"
    screenshots = run_dir / "screenshots"
    fixtures.mkdir(parents=True, exist_ok=True)
    screenshots.mkdir(parents=True, exist_ok=True)
    html = fixtures / "no-model-validation.html"
    status = fixtures / "status.json"
    screenshot = screenshots / "no-model-validation.png"
    html.write_text(
        "\n".join(
            [
                "<!doctype html>",
                "<html>",
                "<body>",
                "<section id=\"no-model-validation\">No-model validation ready</section>",
                "</body>",
                "</html>",
                "",
            ]
        ),
        encoding="utf-8",
    )
    write_json(status, {"status": "ready", "validation": {"tier0": True, "ai_calls_used": 0}})
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:
        raise SystemExit("Pillow is required for no-model validation image evidence") from exc
    image = Image.new("RGB", (800, 480), (18, 18, 18))
    draw = ImageDraw.Draw(image)
    draw.rectangle((40, 40, 760, 440), outline=(255, 102, 0), width=6)
    draw.rectangle((80, 110, 720, 180), fill=(255, 102, 0))
    draw.text((100, 130), "No-model validation ready", fill=(0, 0, 0))
    image.save(screenshot)
    return {"html": html, "status": status, "screenshot": screenshot}


def markdown_summary(summary: dict[str, Any]) -> str:
    lines = [
        "# No-model Validation E2E",
        "",
        f"- Passed: `{summary['passed']}`",
        f"- Automation coverage: `{summary['automation_coverage_percent']}%`",
        f"- AI calls used: `{summary['ai_calls_used']}`",
        f"- Estimated AI cost: `{summary['estimated_ai_cost']}`",
        f"- Total duration: `{summary['total_duration_ms']} ms`",
        "",
        "## Commands",
        "",
        "| Command | Exit | Duration |",
        "| --- | ---: | ---: |",
    ]
    for item in summary["commands"]:
        lines.append(f"| `{' '.join(item['command'])}` | {item['exit_code']} | {item['duration_ms']} ms |")
    lines.extend(
        [
            "",
            "## Outputs",
            "",
        ]
    )
    for key, value in summary["outputs"].items():
        lines.append(f"- {key}: `{value}`")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run no-model validation manifest generation, preflight, and Tier 0 E2E.")
    parser.add_argument("--run-dir", default=str(DEFAULT_RUN_DIR))
    args = parser.parse_args()

    run_dir = Path(args.run_dir).expanduser()
    if not run_dir.is_absolute():
        run_dir = ROOT / run_dir
    run_dir.mkdir(parents=True, exist_ok=True)
    total_start = time.perf_counter()
    started_at = now_iso()
    fixtures = write_fixture_files(run_dir)
    story_path = run_dir / "story.json"
    validation_path = run_dir / "validation.json"
    tier0_dir = run_dir / "tier0"

    commands: list[dict[str, Any]] = []
    story_cmd = [
        "python3",
        "scripts/story_manifest.py",
        "draft",
        "--title",
        "No-model validation generated-manifest E2E",
        "--package",
        "no-model-validation/e2e",
        "--goal",
        "Prove that a feature interpretation can produce story and validation manifests, preflight them, and run Tier 0 without model calls.",
        "--run-dir",
        rel(run_dir),
        "--validation-manifest",
        rel(validation_path),
        "--output",
        rel(story_path),
        "--owner",
        "validator",
        "--node",
        "linux",
        "--role",
        "validator",
        "--acceptance",
        "HTML evidence includes the no-model validation section.",
        "--acceptance",
        "JSON evidence declares Tier 0 ready.",
        "--acceptance",
        "Screenshot evidence is nonblank.",
        "--expected-output",
        f"{rel(fixtures['html'])}::HTML no-model validation evidence",
        "--expected-output",
        f"{rel(fixtures['status'])}::JSON no-model validation evidence",
        "--expected-output",
        f"{rel(fixtures['screenshot'])}::Screenshot no-model validation evidence",
        "--required-text",
        f"{rel(fixtures['html'])}::No-model validation ready::HTML contains section",
        "--json-field",
        f"{rel(fixtures['status'])}::validation.tier0::true",
        "--json-field",
        f"{rel(fixtures['status'])}::validation.ai_calls_used::0",
        "--screenshot",
        f"{rel(fixtures['screenshot'])}::No-model validation screenshot::800,480",
        "--validation-command",
        "python3 -m json.tool fixtures/status.json",
    ]
    result = run_command(story_cmd)
    commands.append(result)
    require_ok(result)

    validation_cmd = ["python3", "scripts/validation_manifest.py", "draft", rel(story_path), "--output", rel(validation_path)]
    result = run_command(validation_cmd)
    commands.append(result)
    require_ok(result)

    preflight_cmd = [
        "python3",
        "scripts/agent_work.py",
        "preflight",
        rel(story_path),
        "--validation-manifest",
        rel(validation_path),
        "--report",
        rel(run_dir / "preflight.json"),
        "--json",
    ]
    result = run_command(preflight_cmd)
    commands.append(result)
    require_ok(result)

    tier0_cmd = ["python3", "scripts/validator_tier0.py", "run", rel(validation_path), "--run-dir", rel(tier0_dir)]
    result = run_command(tier0_cmd)
    commands.append(result)
    require_ok(result)

    validation_payload = json.loads(validation_path.read_text(encoding="utf-8"))
    tier0_result = json.loads((tier0_dir / "validation-result.json").read_text(encoding="utf-8"))
    total_duration_ms = round((time.perf_counter() - total_start) * 1000, 3)
    summary = {
        "schema": "cento.no-model-validation.e2e.v1",
        "started_at": started_at,
        "ended_at": now_iso(),
        "run_dir": rel(run_dir),
        "passed": tier0_result["decision"] == "approve" and all(item["exit_code"] == 0 for item in commands),
        "automation_coverage_percent": validation_payload["coverage"]["automation_coverage_percent"],
        "manual_review_count": validation_payload["coverage"]["manual_review_items"],
        "ai_calls_used": tier0_result["ai_calls_used"],
        "estimated_ai_cost": tier0_result["estimated_ai_cost"],
        "total_duration_ms": total_duration_ms,
        "commands": commands,
        "outputs": {
            "story_manifest": rel(story_path),
            "validation_manifest": rel(validation_path),
            "preflight": rel(run_dir / "preflight.json"),
            "tier0_result": tier0_result["outputs"]["result"],
            "tier0_summary": tier0_result["outputs"]["summary"],
            "summary": rel(run_dir / "e2e-summary.json"),
        },
    }
    write_json(run_dir / "e2e-summary.json", summary)
    (run_dir / "e2e-summary.md").write_text(markdown_summary(summary), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
