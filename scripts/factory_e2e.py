#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
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


def run_step(name: str, command: list[str]) -> dict[str, Any]:
    start = time.perf_counter()
    proc = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    duration_ms = round((time.perf_counter() - start) * 1000, 3)
    return {
        "name": name,
        "command": " ".join(command),
        "exit_code": proc.returncode,
        "passed": proc.returncode == 0,
        "duration_ms": duration_ms,
        "stdout_tail": proc.stdout[-1200:],
        "stderr_tail": proc.stderr[-1200:],
    }


def request_for_fixture(fixture: str) -> str:
    if fixture == "career-consulting":
        return "develop me a career consulting module"
    return f"develop me a {fixture} module"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the no-model Cento Factory planning E2E.")
    parser.add_argument("--fixture", default="career-consulting")
    parser.add_argument("--out", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    out = repo_path(args.out)
    if out.exists():
        shutil.rmtree(out)
    out.parent.mkdir(parents=True, exist_ok=True)

    request = request_for_fixture(args.fixture)
    checks = [
        ("intake", ["python3", "scripts/factory.py", "intake", request, "--dry-run", "--out", rel(out)]),
        ("plan", ["python3", "scripts/factory.py", "plan", rel(out), "--no-model"]),
        ("validate-plan", ["python3", "scripts/factory_plan.py", "validate", rel(out / "factory-plan.json")]),
        ("materialize", ["python3", "scripts/factory.py", "materialize", rel(out)]),
        ("queue", ["python3", "scripts/factory.py", "queue", rel(out)]),
        ("create-issues-preview", ["python3", "scripts/factory.py", "create-issues", rel(out), "--dry-run"]),
        ("dispatch-dry-run", ["python3", "scripts/factory.py", "dispatch", rel(out), "--lane", "builder", "--max", "4", "--include-waiting"]),
        ("integrate-dry-run", ["python3", "scripts/factory.py", "integrate", rel(out), "--dry-run"]),
        ("render-hub", ["python3", "scripts/factory.py", "render-hub", rel(out)]),
    ]
    results = [run_step(name, command) for name, command in checks]

    for story in sorted((out / "tasks").glob("*/story.json")):
        results.append(run_step(f"story:{story.parent.name}", ["python3", "scripts/story_manifest.py", "validate", rel(story)]))
    for validation in sorted((out / "tasks").glob("*/validation.json")):
        results.append(run_step(f"validation:{validation.parent.name}", ["python3", "scripts/validation_manifest.py", "validate", rel(validation)]))

    total_duration_ms = round(sum(float(item["duration_ms"]) for item in results), 3)
    summary = {
        "schema_version": "factory-e2e-summary/v1",
        "fixture": args.fixture,
        "run_dir": rel(out),
        "decision": "approve" if all(item["passed"] for item in results) else "blocked",
        "checks": results,
        "stats": {
            "total_duration_ms": total_duration_ms,
            "ai_calls_used": 0,
            "estimated_ai_cost_usd": 0,
            "validated_by": "factory-e2e",
            "validated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        },
    }
    (out / "validation-summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    release_result = run_step("release", ["python3", "scripts/factory.py", "release", rel(out), "--json"])
    results.append(release_result)
    total_duration_ms = round(sum(float(item["duration_ms"]) for item in results), 3)
    summary["checks"] = results
    summary["decision"] = "approve" if all(item["passed"] for item in results) else "blocked"
    summary["stats"]["total_duration_ms"] = total_duration_ms
    summary["stats"]["validated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    (out / "validation-summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "e2e-summary.md").write_text(
        "\n".join(
            [
                "# Factory Planning E2E",
                "",
                f"- Fixture: `{args.fixture}`",
                f"- Decision: `{summary['decision']}`",
                f"- Total duration ms: `{total_duration_ms}`",
                "- AI calls used: `0`",
                "",
                "## Checks",
                "",
                *[
                    f"- {'PASS' if item['passed'] else 'FAIL'} `{item['name']}` in `{item['duration_ms']}` ms"
                    for item in results
                ],
                "",
            ]
        ),
        encoding="utf-8",
    )
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"decision: {summary['decision']}")
        print(f"total_duration_ms: {total_duration_ms}")
        print("ai_calls_used: 0")
        print(f"validation_summary: {rel(out / 'validation-summary.json')}")
    return 0 if summary["decision"] == "approve" else 1


if __name__ == "__main__":
    raise SystemExit(main())
