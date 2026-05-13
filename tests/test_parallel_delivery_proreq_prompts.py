#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import parallel_delivery_prompts as prompts  # noqa: E402


ROOT = Path(__file__).resolve().parent.parent
PROMPT_TOOL = ROOT / "scripts" / "parallel_delivery_prompts.py"
PARALLEL_TOOL = ROOT / "scripts" / "parallel_delivery.py"
FIXED_TS = "2026-01-01T00:00:00Z"
REQUIRED = [
    "## Mission",
    "## Owned Paths",
    "## Codex Output Format",
    "## Validation Plan",
    "## Evidence To Write",
    "## Safety Rules",
]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_fixture(tmp_path: Path, count: int = 20, lane: str = "all", *, copy_to_temp: bool = False) -> Path:
    run_dir = tmp_path / f"proreq-{count}-{lane}"
    prompts.build_proreq_fixture(
        run_dir,
        copy_to_temp=copy_to_temp,
        count=count,
        lane=lane,
        run_id=f"proreq-{count}-{lane}",
        temp_dir=tmp_path / "temp" / f"proreq-{count}-{lane}",
        timestamp=FIXED_TS,
    )
    return run_dir


def prompt_paths(run_dir: Path) -> list[Path]:
    return sorted((run_dir / "prompts").glob("prompt-*.md"))


def test_20_prompt_fixture_creates_exactly_20_prompts(tmp_path: Path) -> None:
    run_dir = build_fixture(tmp_path, 20)

    assert len(prompt_paths(run_dir)) == 20
    bundle = read_json(run_dir / "prompt-bundle.json")
    assert bundle["schema_version"] == 1
    assert bundle["artifact_type"] == "prompt-bundle"
    assert bundle["prompt_count"] == 20
    assert bundle["requested_count"] == 20
    assert len(bundle["prompts"]) == 20
    assert (run_dir / "prompts" / "prompt-0001-master.md").exists()
    assert (run_dir / "prompts" / "prompt-0020-evidence.md").exists()


def test_15_prompt_fixture_creates_exactly_15_prompts(tmp_path: Path) -> None:
    run_dir = build_fixture(tmp_path, 15)

    assert len(prompt_paths(run_dir)) == 15
    assert read_json(run_dir / "prompt-bundle.json")["prompt_count"] == 15
    assert prompts.validate_prompt_bundle(run_dir)["ok"] is True


def test_prompt_index_references_every_prompt_and_hashes_match(tmp_path: Path) -> None:
    run_dir = build_fixture(tmp_path, 20)
    index = read_json(run_dir / "prompt-index.json")
    paths = {path.name for path in prompt_paths(run_dir)}

    assert len(index["prompts"]) == 20
    for entry in index["prompts"]:
        path = run_dir / entry["path"]
        assert path.name in paths
        assert prompts.sha256_file(path) == entry["sha256"]


def test_every_generated_prompt_includes_required_sections_and_schema(tmp_path: Path) -> None:
    run_dir = build_fixture(tmp_path, 20)

    for path in prompt_paths(run_dir):
        text = path.read_text(encoding="utf-8")
        for heading in REQUIRED:
            assert heading in text, f"{path.name} missing {heading}"
        assert "CODEx_THREAD_TITLE" in text
        assert "PASTE_TO_CODEX" in text
        assert "Do not ask clarifying questions." in text


def test_lane_filter_generates_lane_scoped_prompts(tmp_path: Path) -> None:
    run_dir = build_fixture(tmp_path, 15, lane="builder")
    bundle = read_json(run_dir / "prompt-bundle.json")
    non_master = [entry for entry in bundle["prompts"] if entry["prompt_type"] != "master"]

    assert bundle["lane_filter"] == "builder"
    assert bundle["prompt_count"] == 15
    assert non_master
    assert {entry["lane"] for entry in non_master} == {"builder"}
    assert prompts.validate_prompt_bundle(run_dir)["ok"] is True


def test_master_prompt_exists_and_is_first(tmp_path: Path) -> None:
    run_dir = build_fixture(tmp_path, 20)
    index = read_json(run_dir / "prompt-index.json")

    assert index["prompts"][0]["prompt_id"] == "prompt-0001"
    assert index["prompts"][0]["prompt_type"] == "master"
    assert index["prompts"][0]["path"] == "prompts/prompt-0001-master.md"


def test_copy_to_temp_writes_temp_bridge_files(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CENTO_TEMP_COMMAND_DIR", str(tmp_path / "temp-commands"))
    run_dir = build_fixture(tmp_path, 20, copy_to_temp=True)
    bridge = read_json(run_dir / "temp-bridge.json")
    current = ROOT / bridge["current_prompt"] if not Path(bridge["current_prompt"]).is_absolute() else Path(bridge["current_prompt"])

    assert bridge["schema_version"] == 1
    assert bridge["artifact_type"] == "temp-bridge"
    assert bridge["cento_temp_supported"] is True
    assert current.exists()
    assert (run_dir / "temp-current-prompt.md").exists()
    assert (tmp_path / "temp-commands" / "cento-dev-scale-pro-prompt.json").exists()


def test_generator_policy_is_local_only_and_requires_no_api_calls() -> None:
    policy = prompts.print_policy()

    assert policy["no_api_calls_by_default"] is True
    assert policy["no_live_ai_calls"] is True
    assert policy["no_secrets"] is True
    assert "## Mission" in policy["required_sections"]
    assert "## Codex Output Format" in policy["required_sections"]


def test_secret_like_request_text_is_redacted(tmp_path: Path) -> None:
    run_dir = tmp_path / "secret-redaction"
    prompts.write_fixture_inputs(run_dir, run_id="secret-redaction", timestamp=FIXED_TS)
    request_path = run_dir / "request.md"
    request_path.write_text("# Request\n\nUse token=supersecrettoken123 and sk-abcdefghijklmnopqrstuvwxyz.\n", encoding="utf-8")

    result = prompts.write_prompt_bundle(
        prompts.PromptBundleRequest(
            count=15,
            fixed_timestamp=FIXED_TS,
            lane="all",
            run_dir=run_dir,
            run_id="secret-redaction",
        )
    )

    assert result.errors == []
    prompt_text = (run_dir / "prompts" / "prompt-0001-master.md").read_text(encoding="utf-8")
    assert "supersecrettoken123" not in prompt_text
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in prompt_text
    assert "[REDACTED_SECRET]" in prompt_text


def test_prompt_tool_cli_json_emits_valid_json(tmp_path: Path) -> None:
    run_dir = tmp_path / "cli-tool"
    result = subprocess.run(
        [
            sys.executable,
            str(PROMPT_TOOL),
            "write-fixture",
            "--run-dir",
            str(run_dir),
            "--run-id",
            "cli-tool",
            "--count",
            "15",
            "--fixed-timestamp",
            FIXED_TS,
            "--json",
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert payload["prompt_count"] == 15


def test_parallel_delivery_cli_prompts_route_json_if_available(tmp_path: Path) -> None:
    run_dir = tmp_path / "cli-route"
    result = subprocess.run(
        [
            sys.executable,
            str(PARALLEL_TOOL),
            "patch-swarm",
            "prompts",
            "--run-dir",
            str(run_dir),
            "--run-id",
            "cli-route",
            "--count",
            "20",
            "--lane",
            "all",
            "--fixed-timestamp",
            FIXED_TS,
            "--json",
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert payload["prompt_count"] == 20
