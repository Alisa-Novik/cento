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


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def repo_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else ROOT / path


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_step(name: str, command: list[str], *, allowed_exit_codes: set[int] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    proc = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    allowed = allowed_exit_codes or {0}
    return {
        "name": name,
        "command": " ".join(command),
        "exit_code": proc.returncode,
        "passed": proc.returncode in allowed,
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        "stdout_tail": proc.stdout[-1200:],
        "stderr_tail": proc.stderr[-1200:],
    }


def validate_outputs(out: Path) -> list[str]:
    required = [
        out / "runtime" / "factory-runtime-task-01" / "adapter-run.json",
        out / "runtime" / "factory-runtime-task-01" / "collect-result.json",
        out / "runtime" / "factory-runtime-task-02" / "patch" / "patch.json",
        out / "runtime" / "factory-runtime-task-02" / "launch-plan.json",
        out / "patches" / "factory-runtime-task-02" / "patch.json",
        out / "runtime" / "factory-runtime-task-03" / "launch-plan.json",
    ]
    errors = [f"missing {rel(path)}" for path in required if not path.exists()]
    codex_plan = out / "runtime" / "factory-runtime-task-03" / "launch-plan.json"
    if codex_plan.exists():
        payload = json.loads(codex_plan.read_text(encoding="utf-8"))
        if payload.get("execute_supported") is not False:
            errors.append("codex-dry-run must not support execute")
        if not payload.get("dry_run_command"):
            errors.append("codex-dry-run dry_run_command missing")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Factory runtime adapter zero-AI E2E.")
    parser.add_argument("--out", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    out = repo_path(args.out)
    if out.exists():
        shutil.rmtree(out)
    checks = [
        run_step(
            "fixture",
            [
                "python3",
                "scripts/factory_autopilot_runtime_e2e.py",
                "--fixture",
                "complex-project",
                "--tasks",
                "50",
                "--out",
                rel(out),
            ],
        ),
        run_step("runtime-list", ["python3", "scripts/factory_runtime.py", "list", "--json"]),
        run_step("noop-prepare", ["python3", "scripts/factory_runtime.py", "prepare", rel(out), "--task", "factory-runtime-task-01", "--runtime", "noop", "--dry-run"]),
        run_step("noop-launch", ["python3", "scripts/factory_runtime.py", "launch", rel(out), "--task", "factory-runtime-task-01", "--runtime", "noop", "--dry-run"]),
        run_step("noop-status", ["python3", "scripts/factory_runtime.py", "status", rel(out), "--task", "factory-runtime-task-01", "--json"]),
        run_step("noop-collect", ["python3", "scripts/factory_runtime.py", "collect", rel(out), "--task", "factory-runtime-task-01"]),
        run_step("noop-cancel", ["python3", "scripts/factory_runtime.py", "cancel", rel(out), "--task", "factory-runtime-task-01", "--dry-run"]),
        run_step("fixture-prepare", ["python3", "scripts/factory_runtime.py", "prepare", rel(out), "--task", "factory-runtime-task-02", "--runtime", "local-shell-fixture", "--dry-run"]),
        run_step("fixture-launch", ["python3", "scripts/factory_runtime.py", "launch", rel(out), "--task", "factory-runtime-task-02", "--runtime", "local-shell-fixture", "--dry-run"]),
        run_step("fixture-collect", ["python3", "scripts/factory_runtime.py", "collect", rel(out), "--task", "factory-runtime-task-02"]),
        run_step("codex-prepare", ["python3", "scripts/factory_runtime.py", "prepare", rel(out), "--task", "factory-runtime-task-03", "--runtime", "codex-dry-run", "--dry-run"]),
        run_step("codex-launch", ["python3", "scripts/factory_runtime.py", "launch", rel(out), "--task", "factory-runtime-task-03", "--runtime", "codex-dry-run", "--dry-run"]),
        run_step("integrate-dry-run-artifacts", ["python3", "scripts/factory.py", "integrate", rel(out), "--dry-run"], allowed_exit_codes={0, 1}),
    ]
    errors = validate_outputs(out)
    checks.append({"name": "runtime-output-contract", "command": "internal validation", "exit_code": 0 if not errors else 1, "passed": not errors, "duration_ms": 0, "stdout_tail": "", "stderr_tail": "; ".join(errors)})
    decision = "approve" if all(item["passed"] for item in checks) else "blocked"
    summary = {
        "schema_version": "factory-runtime-adapters-e2e-summary/v1",
        "package": "factory-runtime-adapters-v1",
        "run_dir": rel(out),
        "decision": decision,
        "checks": checks,
        "ai_calls_used": 0,
        "estimated_cost_usd": 0,
        "generated_at": now_iso(),
    }
    write_json(out / "runtime-adapters-e2e-summary.json", summary)
    (out / "runtime-adapters-e2e-summary.md").write_text(
        "\n".join(
            [
                "# Factory Runtime Adapters E2E",
                "",
                f"- Decision: `{decision}`",
                "- AI calls used: 0",
                "- Estimated cost USD: 0",
                "",
                "## Checks",
                "",
                *[f"- {'PASS' if item['passed'] else 'FAIL'} `{item['name']}`" for item in checks],
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True) if args.json else f"summary: {rel(out / 'runtime-adapters-e2e-summary.md')}")
    return 0 if decision == "approve" else 1


if __name__ == "__main__":
    raise SystemExit(main())
