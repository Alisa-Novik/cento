#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from datetime import datetime, timezone
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
    return {
        "name": name,
        "command": " ".join(command),
        "exit_code": proc.returncode,
        "passed": proc.returncode == 0,
        "duration_ms": round((time.perf_counter() - start) * 1000, 3),
        "stdout_tail": proc.stdout[-1600:],
        "stderr_tail": proc.stderr[-1600:],
    }


def request_for_fixture(fixture: str) -> str:
    if fixture == "career-consulting":
        return "develop me a career consulting module"
    return f"develop me a {fixture} module"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the zero-AI Factory dispatch control-plane E2E.")
    parser.add_argument("--fixture", default="career-consulting")
    parser.add_argument("--out", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    out = repo_path(args.out)
    if out.exists():
        shutil.rmtree(out)
    out.parent.mkdir(parents=True, exist_ok=True)

    request = request_for_fixture(args.fixture)
    run_arg = rel(out)
    checks = [
        ("intake", ["python3", "scripts/factory.py", "intake", request, "--dry-run", "--out", run_arg]),
        ("plan", ["python3", "scripts/factory.py", "plan", run_arg, "--no-model"]),
        ("validate-plan", ["python3", "scripts/factory_plan.py", "validate", rel(out / "factory-plan.json")]),
        ("materialize", ["python3", "scripts/factory.py", "materialize", run_arg]),
        ("queue", ["python3", "scripts/factory.py", "queue", run_arg]),
        ("queue-validate", ["python3", "scripts/factory_queue.py", "validate", rel(out / "queue" / "queue.json")]),
        ("preflight", ["python3", "scripts/factory.py", "preflight", run_arg, "--json"]),
        ("lease-dry-run", ["python3", "scripts/factory.py", "lease", run_arg, "--task", "crm-schema-extension", "--dry-run"]),
        ("dispatch-dry-run", ["python3", "scripts/factory.py", "dispatch", run_arg, "--lane", "builder", "--max", "4", "--dry-run"]),
        ("collect", ["python3", "scripts/factory.py", "collect", run_arg]),
        ("integrate-dry-run", ["python3", "scripts/factory.py", "integrate", run_arg, "--dry-run"]),
        ("validate", ["python3", "scripts/factory.py", "validate", run_arg]),
        ("render-hub", ["python3", "scripts/factory.py", "render-hub", run_arg]),
        ("status", ["python3", "scripts/factory.py", "status", run_arg, "--json"]),
    ]
    results = [run_step(name, command) for name, command in checks]
    total_duration_ms = round(sum(float(item["duration_ms"]) for item in results), 3)
    decision = "approve" if all(item["passed"] for item in results) else "blocked"
    summary = {
        "schema_version": "factory-dispatch-e2e-summary/v1",
        "fixture": args.fixture,
        "run_dir": run_arg,
        "decision": decision,
        "checks": results,
        "stats": {
            "total_duration_ms": total_duration_ms,
            "ai_calls_used": 0,
            "estimated_ai_cost_usd": 0,
            "validated_by": "factory-dispatch-e2e",
            "validated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        },
    }
    (out / "e2e-summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "e2e-summary.md").write_text(
        "\n".join(
            [
                "# Factory Dispatch Zero-AI E2E",
                "",
                f"- Fixture: `{args.fixture}`",
                f"- Decision: `{decision}`",
                f"- Total duration ms: `{total_duration_ms}`",
                "- AI calls used: 0",
                "",
                "## Checks",
                "",
                *[f"- {'PASS' if item['passed'] else 'FAIL'} `{item['name']}` in `{item['duration_ms']}` ms" for item in results],
                "",
            ]
        ),
        encoding="utf-8",
    )
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"decision: {decision}")
        print(f"total_duration_ms: {total_duration_ms}")
        print("AI calls used: 0")
        print(f"summary: {rel(out / 'e2e-summary.md')}")
    return 0 if decision == "approve" else 1


if __name__ == "__main__":
    raise SystemExit(main())
