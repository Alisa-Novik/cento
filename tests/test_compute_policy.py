#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "compute_policy.py"


def run_policy(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["CENTO_COMPUTE_POLICY_PATH"] = str(tmp_path / "compute-policy.json")
    env["CENTO_AGENT_RUNTIME_CONFIG"] = str(tmp_path / "agent-runtimes.json")
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        env=env,
    )


def test_codex_first_preset_writes_policy_and_runtime_weights(tmp_path: Path) -> None:
    result = run_policy(tmp_path, "preset", "codex-first", "--json")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["provider_shares"] == {"codex": 85, "claude": 15, "openai_api": 0}

    policy = json.loads((tmp_path / "compute-policy.json").read_text())
    assert policy["profile"] == "codex-first"
    assert policy["providers"]["openai_api"]["enabled"] is False

    registry = json.loads((tmp_path / "agent-runtimes.json").read_text())
    weights = {item["id"]: item["weight"] for item in registry["runtimes"]}
    assert weights == {"codex": 85, "claude-code": 15}
    assert registry["compute_policy"]["openai_api_share"] == 0


def test_set_rejects_zero_agent_share(tmp_path: Path) -> None:
    result = run_policy(tmp_path, "set", "--codex", "0", "--claude", "0", "--openai-api", "100")

    assert result.returncode == 2
    assert "at least one agent runtime share is required" in result.stderr


def test_agent_preferred_preset_records_utilization_threshold(tmp_path: Path) -> None:
    result = run_policy(tmp_path, "preset", "agent-preferred", "--json")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["provider_shares"] == {"codex": 55, "claude": 20, "openai_api": 25}
    assert payload["agent_preference_policy"]["codex_claude_utilization_threshold_percent"] == 30
    assert payload["agent_preference_policy"]["eligible_work_agent_preference_percent_range"] == [70, 80]

    policy = json.loads((tmp_path / "compute-policy.json").read_text())
    assert policy["agent_preference_policy"]["eligible_work_agent_preference_target_percent"] == 75
    assert policy["metered_api_policy"]["agent_preference_policy"]["codex_claude_utilization_threshold_percent"] == 30
