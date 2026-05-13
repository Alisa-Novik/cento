#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import parallel_delivery_codex_packets as packets  # noqa: E402


ROOT = Path(__file__).resolve().parent.parent
FIXED_TS = "2026-01-01T00:00:00Z"
REQUIRED_SECTIONS = [
    "## Thread Title",
    "## Task ID",
    "## Mission",
    "## Discovery Commands",
    "## Owned Write Paths",
    "## Read-Only Paths",
    "## Prohibited Paths",
    "## Implementation Steps",
    "## Expected Files Changed",
    "## Tests And Validation",
    "## Evidence Path",
    "## Patch Bundle Output Instructions",
    "## Handoff Note Format",
    "## Failure / Blocker Protocol",
    "## Safety Rules",
    "## Acceptance Criteria",
]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_fixture(tmp_path: Path, run_id: str = "codex-packets-fixture") -> Path:
    run_dir = tmp_path / run_id
    result = packets.build_codex_packets_fixture(run_dir, run_id=run_id, count=10, timestamp=FIXED_TS)
    assert not result.errors
    return run_dir


def test_fixture_creates_at_least_10_packets_and_lanes(tmp_path: Path) -> None:
    run_dir = build_fixture(tmp_path)
    index = read_json(run_dir / "codex-packet-index.json")

    assert index["packet_count"] >= 10
    assert len(index["packets"]) >= 10
    lanes = {item["lane"] for item in index["packets"]}
    assert {"builder", "validator", "docs-evidence", "coordinator", "integrator"} <= lanes


def test_index_references_every_packet_and_hashes_match(tmp_path: Path) -> None:
    run_dir = build_fixture(tmp_path)
    index = read_json(run_dir / "codex-packet-index.json")

    for item in index["packets"]:
        path = run_dir / item["path"]
        assert path.exists(), item
        assert packets.sha256_file(path) == item["sha256"]


def test_bundle_is_deterministic_and_parseable(tmp_path: Path) -> None:
    first = build_fixture(tmp_path, "deterministic-fixture")
    first_bundle = (first / "codex-packet-bundle.json").read_text(encoding="utf-8")
    second = build_fixture(tmp_path, "deterministic-fixture")
    second_bundle = (second / "codex-packet-bundle.json").read_text(encoding="utf-8")

    assert json.loads(first_bundle)["artifact_type"] == "codex-packet-bundle"
    assert first_bundle == second_bundle


def test_every_packet_has_required_sections_and_protocols(tmp_path: Path) -> None:
    run_dir = build_fixture(tmp_path)
    for path in sorted((run_dir / "packets").glob("*-codex-packet.md")):
        text = path.read_text(encoding="utf-8")
        assert text.startswith("# Codex Worker Packet")
        for section in REQUIRED_SECTIONS:
            assert section in text, f"{path.name} missing {section}"
        assert "Patch Bundle Output Instructions" in text
        assert "Handoff Note Format" in text
        assert "Failure / Blocker Protocol" in text
        assert "Do not edit files outside Owned Write Paths." in text
        assert ".env.mcp" in text


def test_owned_paths_non_overlapping_and_read_only_shared(tmp_path: Path) -> None:
    run_dir = build_fixture(tmp_path)
    index = read_json(run_dir / "codex-packet-index.json")
    owned: list[tuple[str, str]] = []
    read_only_sets = []
    for item in index["packets"]:
        assert item["owned_write_paths"]
        assert item["read_only_paths"] is not None
        read_only_sets.append(tuple(item["read_only_paths"]))
        for path in item["owned_write_paths"]:
            assert not path.startswith("/")
            assert ".." not in path.split("/")
            owned.append((item["task_id"], path.rstrip("/")))
    for index_a, (task_a, path_a) in enumerate(owned):
        for task_b, path_b in owned[index_a + 1 :]:
            assert not (path_a == path_b or path_a.startswith(path_b + "/") or path_b.startswith(path_a + "/"))
    assert len(set(read_only_sets)) == 1


def test_packets_do_not_contain_secret_like_fixture_values(tmp_path: Path) -> None:
    run_dir = build_fixture(tmp_path)
    secret_value = re.compile(r"OPENAI_API_KEY\s*=|sk-[A-Za-z0-9_-]{16,}|\b(token|password|api_key)\s*=", re.I)
    for path in sorted((run_dir / "packets").glob("*-codex-packet.md")):
        assert not secret_value.search(path.read_text(encoding="utf-8"))


def test_validate_bundle_reports_ok(tmp_path: Path) -> None:
    run_dir = build_fixture(tmp_path)
    validation = packets.validate_packet_bundle(run_dir)

    assert validation["ok"] is True
    assert validation["packet_count"] >= 10
    assert validation["errors"] == []


def test_cli_json_emits_valid_json(tmp_path: Path) -> None:
    run_dir = tmp_path / "cli-codex-packets"
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "parallel_delivery.py"),
            "patch-swarm",
            "worker-packets",
            "--run-dir",
            str(run_dir),
            "--run-id",
            "cli-codex-packets-fixture",
            "--fixture",
            "--count",
            "10",
            "--fixed-timestamp",
            FIXED_TS,
            "--json",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["packet_count"] >= 10
