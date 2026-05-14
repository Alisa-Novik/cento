from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data" / "patch-swarm-pro-calls.json"
SCRIPT = ROOT / "scripts" / "patch_swarm_pro_calls.py"


def load_registry(path: Path = REGISTRY) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_helper(*args: str, registry: Path | None = None) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(SCRIPT)]
    if registry is not None:
        command.extend(["--registry", str(registry)])
    command.extend(args)
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True)


def copy_registry(tmp_path: Path) -> Path:
    target = tmp_path / "patch-swarm-pro-calls.json"
    target.write_text(REGISTRY.read_text(encoding="utf-8"), encoding="utf-8")
    return target


def test_registry_has_part1_prompts_and_future_placeholders() -> None:
    registry = load_registry()

    assert registry["schema_version"] == "cento.patch_swarm.pro_call_registry.v1"
    assert len(registry["calls"]) == 101
    for index, call in enumerate(registry["calls"]):
        assert call["call_id"] == index
        assert call["call_label"] == f"CALL {index:02d}"
        assert call["status"] in {"PENDING", "IN_PROGRESS", "CODEX_DONE", "CLOSED", "BLOCKED"}
        assert isinstance(call["Pro_output"], str)
        assert call["Pro_output"] == ""
        assert isinstance(call["prompt"], str)
        if index <= 30:
            assert call["part"] == 1
            assert call["placeholder"] is False
            assert call["prompt"].startswith(f"## CALL {index:02d}:")
        elif index <= 60:
            assert call["part"] == 2
            assert call["placeholder"] is True
            assert call["prompt"] == ""
        else:
            assert call["part"] == 3
            assert call["placeholder"] is True
            assert call["prompt"] == ""


def test_validate_command_accepts_registry() -> None:
    result = run_helper("validate", "--json")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "pass"
    assert payload["counts"]["PENDING"] >= 1


def test_next_prefers_in_progress_then_pending(tmp_path: Path) -> None:
    registry_path = copy_registry(tmp_path)
    registry = load_registry(registry_path)
    registry["calls"][0]["status"] = "IN_PROGRESS"
    registry_path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")

    result = run_helper("next", "--json", registry=registry_path)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["next"]["call_id"] == 0
    assert payload["next"]["status"] == "IN_PROGRESS"


def test_ingest_pro_output_sets_in_progress_and_records_event(tmp_path: Path) -> None:
    registry_path = copy_registry(tmp_path)
    output = tmp_path / "call-000-pro-output.md"
    output.write_text("CODEx_THREAD_TITLE\nRuntime contract packet\n", encoding="utf-8")
    evidence_dir = tmp_path / "evidence"

    result = run_helper(
        "ingest-pro-output",
        "--call-id",
        "0",
        "--file",
        str(output),
        "--evidence-dir",
        str(evidence_dir),
        registry=registry_path,
    )

    assert result.returncode == 0, result.stderr
    registry = load_registry(registry_path)
    call = registry["calls"][0]
    assert call["status"] == "IN_PROGRESS"
    assert call["Pro_output"] == output.read_text(encoding="utf-8")
    assert call["pro_output_received_at"]
    assert call["events"][-1]["event"] == "pro_output_ingested"
    assert (evidence_dir / "call-000-pro-output.md").exists()


def test_ingest_prompt_populates_prompt_without_pro_output(tmp_path: Path) -> None:
    registry_path = copy_registry(tmp_path)
    prompt = tmp_path / "call-000-prompt.md"
    prompt.write_text("# CALL 00: Evidence Inventory\n\nPrompt body.\n", encoding="utf-8")
    evidence_dir = tmp_path / "evidence"

    result = run_helper(
        "ingest-prompt",
        "--call-id",
        "0",
        "--file",
        str(prompt),
        "--evidence-dir",
        str(evidence_dir),
        registry=registry_path,
    )

    assert result.returncode == 0, result.stderr
    registry = load_registry(registry_path)
    call = registry["calls"][0]
    assert call["status"] == "PENDING"
    assert call["placeholder"] is False
    assert call["title"] == "Evidence Inventory"
    assert call["prompt"] == prompt.read_text(encoding="utf-8")
    assert call["Pro_output"] == ""
    assert call["events"][-1]["event"] == "prompt_ingested"
    assert (evidence_dir / "call-000-prompt.md").exists()


def test_ingest_secret_like_output_blocks_call(tmp_path: Path) -> None:
    registry_path = copy_registry(tmp_path)
    output = tmp_path / "call-000-pro-output.md"
    output.write_text("OPENAI_API_KEY=sk-" + ("A" * 32), encoding="utf-8")

    result = run_helper(
        "ingest-pro-output",
        "--call-id",
        "0",
        "--file",
        str(output),
        registry=registry_path,
    )

    assert result.returncode == 2
    registry = load_registry(registry_path)
    call = registry["calls"][0]
    assert call["status"] == "BLOCKED"
    assert call["Pro_output"] == ""
    assert call["events"][-1]["event"] == "pro_output_rejected"


def test_invalid_status_transition_fails_without_force(tmp_path: Path) -> None:
    registry_path = copy_registry(tmp_path)

    result = run_helper("set-status", "--call-id", "0", "--status", "CLOSED", registry=registry_path)

    assert result.returncode != 0
    assert "invalid transition" in result.stderr
