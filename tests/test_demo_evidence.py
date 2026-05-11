#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "demo_evidence.py"


def run_demo_evidence(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


def test_record_dry_run_writes_receipt_and_summary(tmp_path: Path) -> None:
    out = tmp_path / "dry-run"
    result = run_demo_evidence(
        "record",
        "--duration",
        "15",
        "--dry-run",
        "--recorder",
        "synthetic",
        "--out",
        str(out),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "cento.demo_evidence.v1"
    assert payload["status"] == "dry_run"
    assert payload["duration_window_seconds"] == {"min": 10.0, "max": 30.0}
    assert payload["recorder"] == "synthetic"
    assert (out / "receipt.json").exists()
    assert (out / "summary.md").exists()
    assert not (out / "demo.mp4").exists()


def test_record_rejects_clips_outside_short_demo_window(tmp_path: Path) -> None:
    result = run_demo_evidence(
        "record",
        "--duration",
        "9",
        "--dry-run",
        "--recorder",
        "synthetic",
        "--out",
        str(tmp_path / "too-short"),
    )

    assert result.returncode == 2
    assert "between 10 and 30 seconds" in result.stderr


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="synthetic smoke capture requires ffmpeg")
def test_synthetic_capture_verifies_video_receipt(tmp_path: Path) -> None:
    out = tmp_path / "synthetic"
    record = run_demo_evidence(
        "record",
        "--duration",
        "10",
        "--recorder",
        "synthetic",
        "--out",
        str(out),
        "--json",
    )
    assert record.returncode == 0, record.stderr
    payload = json.loads(record.stdout)
    assert payload["status"] == "passed"
    assert payload["video_sha256"]
    assert (out / "demo.mp4").stat().st_size > 0

    verify = run_demo_evidence("verify", str(out), "--json")
    assert verify.returncode == 0, verify.stderr
    result = json.loads(verify.stdout)
    assert result["ok"] is True
    assert all(check["ok"] for check in result["checks"])
