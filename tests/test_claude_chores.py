#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import claude_chores as chores


def configure_roots(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(chores, "ROOT", tmp_path)
    monkeypatch.setattr(chores, "RUN_ROOT", tmp_path / "workspace" / "runs" / "claude-chores")
    monkeypatch.setattr(chores, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(chores, "DOC_PATH", tmp_path / "docs" / "claude-code-chores.md")
    monkeypatch.setattr(chores, "TOOLS_JSON", tmp_path / "data" / "tools.json")


def write_tools(tmp_path: Path, tools: list[dict]) -> None:
    path = tmp_path / "data" / "tools.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"tools": tools}, indent=2) + "\n", encoding="utf-8")


def base_args(**overrides) -> argparse.Namespace:
    values = {
        "scope": "broad-repo",
        "run_dir": "",
        "json": True,
        "chore_limit": 2,
        "max_launch": 2,
        "builder_target": 2,
        "small_target": 1,
        "validator_target": 1,
        "coordinator_target": 0,
        "runtime": "claude-code",
        "model": "claude-sonnet-4-6",
        "dry_run": False,
        "scheduler_trigger": "",
        "interval_minutes": 30,
        "crontab_file": "",
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def completed(command: list[str], stdout: str = "{}", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(command, returncode, stdout=stdout, stderr="")


def test_discovery_detects_missing_registered_entrypoint(monkeypatch, tmp_path: Path) -> None:
    configure_roots(monkeypatch, tmp_path)
    write_tools(
        tmp_path,
        [
            {
                "id": "agent-processes",
                "name": "Agent Processes Dashboard",
                "entrypoint": "./scripts/agent_processes_tui.sh",
            }
        ],
    )

    candidates = chores.discover_candidate_chores("broad-repo", issues=[])

    assert candidates[0]["source"] == "missing-entrypoint:agent-processes"
    assert candidates[0]["owned_paths"][0] == "scripts/agent_processes_tui.sh"
    assert "./scripts/cento.sh docs agent-processes" in candidates[0]["validation_commands"][1]


def test_existing_chore_fingerprint_blocks_duplicate_creation() -> None:
    candidate = chores.make_candidate(
        source="docs-cli-drift:dispatch-pool",
        title="Remove stale agent-work dispatch-pool references",
        description="Fix stale docs.",
        owned_paths=["data/tools.json"],
        acceptance=["Docs are corrected."],
        validation_commands=["python3 -m json.tool data/tools.json"],
        priority=1,
    )
    issues = [
        {
            "id": 123,
            "subject": f"[chore:{candidate['fingerprint']}] Remove stale agent-work dispatch-pool references",
            "package": "claude-chores",
            "status": "Queued",
        }
    ]

    annotated = chores.annotate_existing([candidate], issues)

    assert annotated[0]["existing_issue_id"] == 123
    assert annotated[0]["eligible_to_create"] is False


def test_cron_install_and_uninstall_preserve_other_blocks(monkeypatch, tmp_path: Path, capsys) -> None:
    configure_roots(monkeypatch, tmp_path)
    crontab = tmp_path / "crontab.txt"
    crontab.write_text("# existing\n* * * * * echo keep\n", encoding="utf-8")

    install_args = base_args(crontab_file=str(crontab))
    assert chores.command_install_cron(install_args) == 0
    installed = crontab.read_text(encoding="utf-8")
    assert "* * * * * echo keep" in installed
    assert chores.CRON_BEGIN in installed
    assert "*/30 * * * *" in installed
    assert "claude-chores run --scope broad-repo" in installed
    capsys.readouterr()

    uninstall_args = argparse.Namespace(crontab_file=str(crontab), dry_run=False, json=True)
    assert chores.command_uninstall_cron(uninstall_args) == 0
    uninstalled = crontab.read_text(encoding="utf-8")
    assert "* * * * * echo keep" in uninstalled
    assert chores.CRON_BEGIN not in uninstalled


def test_run_dry_run_writes_artifacts_and_forces_claude_pool(monkeypatch, tmp_path: Path, capsys) -> None:
    configure_roots(monkeypatch, tmp_path)
    write_tools(tmp_path, [{"id": "agent-processes", "name": "Agent Processes", "entrypoint": "./scripts/agent_processes_tui.sh"}])
    monkeypatch.setattr(chores, "agent_work_issues", lambda: [])
    monkeypatch.setattr(chores, "agent_work_active_runs", lambda include_untracked=True: [{"run_id": "untracked-codex-1"}])
    calls: list[tuple[list[str], dict[str, str] | None]] = []

    def fake_run_command(command: list[str], *, env=None, timeout: int = 90):
        calls.append((command, env))
        payload = {"dry_run": True, "reason_summary": {"primary_reason": "dry_run"}}
        return completed(command, stdout=json.dumps(payload))

    monkeypatch.setattr(chores, "run_command", fake_run_command)

    assert chores.command_run(base_args(dry_run=True, run_dir=str(tmp_path / "run"))) == 0
    status = json.loads((tmp_path / "run" / "status.json").read_text(encoding="utf-8"))
    created = json.loads((tmp_path / "run" / "created_issues.json").read_text(encoding="utf-8"))
    assert status["created_count"] == 1
    assert created[0]["status"] == "planned"
    pool_command, pool_env = calls[-1]
    assert "--package" in pool_command
    assert "claude-chores" in pool_command
    assert "--runtime" in pool_command
    assert "claude-code" in pool_command
    assert pool_env["CENTO_AGENT_RUNTIME"] == "claude-code"
    assert (tmp_path / "workspace" / "runs" / "claude-chores" / "latest" / "status.json").exists()
    capsys.readouterr()


def test_run_create_canonicalizes_story_and_validation(monkeypatch, tmp_path: Path, capsys) -> None:
    configure_roots(monkeypatch, tmp_path)
    write_tools(tmp_path, [{"id": "agent-processes", "name": "Agent Processes", "entrypoint": "./scripts/agent_processes_tui.sh"}])
    monkeypatch.setattr(chores, "agent_work_issues", lambda: [])
    monkeypatch.setattr(chores, "agent_work_active_runs", lambda include_untracked=True: [])

    def fake_run_command(command: list[str], *, env=None, timeout: int = 90):
        if command[:3] == ["python3", "scripts/agent_work.py", "create"]:
            return completed(command, stdout=json.dumps({"id": 456, "subject": command[command.index("--title") + 1]}))
        payload = {"dry_run": False, "reason_summary": {"primary_reason": "launched"}}
        return completed(command, stdout=json.dumps(payload))

    monkeypatch.setattr(chores, "run_command", fake_run_command)

    assert chores.command_run(base_args(run_dir=str(tmp_path / "run"))) == 0
    story_path = tmp_path / "workspace" / "runs" / "agent-work" / "456" / "story.json"
    validation_path = story_path.with_name("validation.json")
    story = json.loads(story_path.read_text(encoding="utf-8"))
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    assert story["issue"]["id"] == 456
    assert story["validation"]["manifest"] == "workspace/runs/agent-work/456/validation.json"
    assert validation["story_manifest"] == "workspace/runs/agent-work/456/story.json"
    assert validation["coverage"]["automation_coverage_percent"] == 100.0
    capsys.readouterr()
