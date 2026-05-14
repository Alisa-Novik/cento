#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "tool_foundry.py"
sys.path.insert(0, str(ROOT / "scripts"))
import tool_foundry as tf  # noqa: E402


def run_foundry(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


def test_foundry_e2e_dry_run_passes_with_zero_cost() -> None:
    run_id = f"tool-foundry-test-{os.getpid()}"
    result = run_foundry("e2e", "--dry-run", "--run-id", run_id, "--max-parallel", "6", "--json")

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    run_dir = ROOT / payload["run_dir"]
    validation = json.loads((run_dir / "validation_summary.json").read_text(encoding="utf-8"))
    cost = json.loads((run_dir / "cost_receipt.json").read_text(encoding="utf-8"))
    workset = json.loads((run_dir / "workset.json").read_text(encoding="utf-8"))

    assert payload["status"] == "passed"
    assert payload["mode"] == "dry-run"
    assert validation["status"] == "passed"
    assert cost["actual_cost_usd"] == 0.0
    assert cost["hard_cap_exceeded"] is False
    assert len(workset["tasks"]) == 6
    assert all(path.startswith(("docs/", "standards/")) for task in workset["tasks"] for path in task["write_paths"])


def test_foundry_live_mode_requires_explicit_budget_caps() -> None:
    result = run_foundry("e2e", "--live", "--run-id", f"tool-foundry-live-budget-test-{os.getpid()}", "--json")

    assert result.returncode != 0
    assert "requires both --budget-usd and --max-budget-usd" in result.stderr


def test_foundry_materialize_dry_run_writes_real_file_receipts() -> None:
    run_id = f"tool-foundry-materialize-test-{os.getpid()}"
    created = run_foundry("create", "client intake hub", "--run-id", run_id, "--json")
    assert created.returncode == 0, created.stderr

    result = run_foundry("materialize", run_id, "--dry-run", "--json")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    run_dir = ROOT / payload["run_dir"]
    manifest = json.loads((run_dir / "real_file_manifest.json").read_text(encoding="utf-8"))
    plan = json.loads((run_dir / "materialization_plan.json").read_text(encoding="utf-8"))
    receipt = json.loads((run_dir / "materialization_receipt.json").read_text(encoding="utf-8"))

    assert payload["status"] == "planned"
    assert manifest["schema_version"] == tf.SCHEMA_REAL_FILE_MANIFEST
    assert manifest["target_root"] == tf.DEFAULT_REAL_FILE_TARGET_ROOT
    assert plan["schema_version"] == tf.SCHEMA_MATERIALIZATION_PLAN
    assert receipt["mode"] == "dry-run"
    assert receipt["applied"] is False
    assert {row["target_path"] for row in receipt["files"]} >= {
        "templates/foundry/client-intake-hub/client-intake-hub.html",
        "templates/foundry/client-intake-hub/client-profile.schema.json",
        "docs/client-intake-hub.md",
    }


@pytest.mark.parametrize("target_root", ["../bad", "/tmp/bad", "docs/client-intake-hub"])
def test_foundry_rejects_unsafe_real_file_target_roots(target_root: str) -> None:
    with pytest.raises(ValueError):
        tf.normalize_real_file_target_root(target_root)


def test_foundry_hard_cap_rejects_bill_explosion() -> None:
    result = run_foundry(
        "e2e",
        "--live",
        "--run-id",
        f"tool-foundry-live-hard-cap-test-{os.getpid()}",
        "--budget-usd",
        "10",
        "--max-budget-usd",
        "21",
        "--json",
    )

    assert result.returncode != 0
    assert "hard cap cannot exceed $20" in result.stderr
