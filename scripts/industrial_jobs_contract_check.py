#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def run(cmd: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def build_fixtures(root: Path) -> None:
    now = datetime.now(timezone.utc).isoformat()
    good = root / "good-job"
    write_json(
        good / "job.json",
        {
            "id": "good-job",
            "status": "succeeded",
            "created_at": now,
            "finished_at": now,
            "feature": "Ship stable jobs summary",
            "run_dir": str(good),
            "tasks": [{"id": "build", "title": "Build contract"}, {"id": "validate", "title": "Validate contract"}],
            "results": [
                {"task": "build", "returncode": 0, "log": str(good / "logs" / "build.log")},
                {"task": "validate", "returncode": 0, "log": str(good / "logs" / "validate.log")},
            ],
        },
    )
    (good / "logs").mkdir(parents=True, exist_ok=True)
    (good / "logs" / "build.log").write_text("build ok\n", encoding="utf-8")
    (good / "logs" / "validate.log").write_text("validate ok\n", encoding="utf-8")

    degraded = root / "degraded-job"
    write_json(
        degraded / "job.json",
        {
            "id": "degraded-job",
            "status": "running",
            "created_at": now,
            "feature": "Running job without result logs",
            "run_dir": str(degraded),
            "tasks": [{"id": "build", "title": "Build missing output"}],
            "results": [],
        },
    )

    empty = root / "empty-job"
    write_json(
        empty / "job.json",
        {
            "id": "empty-job",
            "status": "planned",
            "created_at": now,
            "feature": "No task job",
            "run_dir": str(empty),
            "tasks": [],
            "results": [],
        },
    )

    invalid = root / "invalid-job"
    invalid.mkdir(parents=True, exist_ok=True)
    (invalid / "job.json").write_text("{not-json\n", encoding="utf-8")

    # Keep the log-backed good job first in mtime-sorted terminal snapshots.
    os.utime(good / "job.json", None)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def check_python_contract(env: dict[str, str]) -> None:
    code = """
import json
from jobs_server import load_jobs
payload = load_jobs()
print(json.dumps(payload, sort_keys=True))
"""
    result = run([sys.executable, "-c", code], env)
    assert_true(result.returncode == 0, result.stderr or result.stdout)
    payload = json.loads(result.stdout)
    assert_true(payload["state"] == "degraded", f"expected degraded payload state: {payload['state']}")
    jobs = {job["id"]: job for job in payload["jobs"]}
    assert_true(jobs["good-job"]["job_summary"]["task_count"] == 2, "good-job task_count")
    assert_true(jobs["good-job"]["job_summary"]["current_step"] == "Validate contract", "good-job current_step")
    assert_true(jobs["good-job"]["job_summary"]["latest_log"]["exists"], "good-job latest_log")
    assert_true(jobs["degraded-job"]["job_summary"]["state"] == "degraded", "degraded-job state")
    assert_true(jobs["empty-job"]["job_summary"]["state"] == "empty", "empty-job state")
    assert_true(jobs["invalid-job"]["job_summary"]["state"] == "degraded", "invalid-job summary state")


def check_empty_contract(env: dict[str, str], root: Path) -> None:
    empty_root = root / "no-jobs"
    empty_root.mkdir()
    empty_env = dict(env)
    empty_env["CENTO_CLUSTER_JOBS_ROOT"] = str(empty_root)
    result = run([sys.executable, "-c", "from jobs_server import load_jobs; print(load_jobs()['state'])"], empty_env)
    assert_true(result.returncode == 0, result.stderr or result.stdout)
    assert_true(result.stdout.strip() == "empty", f"expected empty state: {result.stdout!r}")


def check_unavailable_contract(env: dict[str, str], root: Path) -> None:
    unavailable_root = root / "unavailable-root"
    unavailable_root.write_text("not a directory\n", encoding="utf-8")
    unavailable_env = dict(env)
    unavailable_env["CENTO_CLUSTER_JOBS_ROOT"] = str(unavailable_root)
    result = run([sys.executable, "scripts/industrial_panel.py", "jobs", "--once", "--plain"], unavailable_env)
    assert_true(result.returncode == 0, result.stderr or result.stdout)
    assert_true("jobs unavailable:" in result.stdout, f"expected unavailable panel output: {result.stdout!r}")


def check_python_panel(env: dict[str, str]) -> None:
    result = run([sys.executable, "scripts/industrial_panel.py", "jobs", "--once", "--plain"], env)
    assert_true(result.returncode == 0, result.stderr or result.stdout)
    stdout = result.stdout.upper()
    assert_true("SELECTED JOB" in stdout, "python panel missing selected job detail")
    assert_true("LATEST LOG" in stdout, "python panel missing latest log detail")
    assert_true("SUMMARY" in stdout, "python panel missing artifact summary path")
    assert_true("TASK STATE" in stdout, "python panel missing task state section")
    assert_true("NEXT" in stdout, "python panel missing next action section")
    assert_true("GOOD-JOB" in stdout, "python panel missing populated job row")
    assert_true("DEGRADED" in stdout, "python panel missing degraded job state")


def check_tui(env: dict[str, str]) -> None:
    result = run(["./scripts/industrial_jobs_tui.sh", "--once"], env)
    assert_true(result.returncode == 0, result.stderr or result.stdout)
    assert_true("GOOD-JOB" in result.stdout.upper(), "tui missing good-job")
    assert_true("DEGRADED" in result.stdout.upper(), "tui missing degraded state")
    assert_true("AGE" in result.stdout, "tui missing AGE column")
    assert_true("SELECTED JOB" in result.stdout, "tui missing selected job detail")
    assert_true("LATEST LOG" in result.stdout, "tui missing latest log detail")
    assert_true("NEXT" in result.stdout, "tui missing next action detail")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="cento-industrial-jobs-") as tmp:
        fixture_root = Path(tmp)
        build_fixtures(fixture_root)
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT / "scripts")
        env["CENTO_CLUSTER_JOBS_ROOT"] = str(fixture_root)
        check_python_contract(env)
        check_empty_contract(env, fixture_root)
        check_unavailable_contract(env, fixture_root)
        check_python_panel(env)
        check_tui(env)
    print("industrial jobs contract check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
