#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import validation_manifest


def test_expected_output_file_checks_use_agent_work_file_type() -> None:
    story = {
        "issue": {"id": 1, "title": "Route evidence", "package": "default"},
        "paths": {"run_dir": "workspace/runs/agent-work/1"},
        "scope": {"goal": "Route evidence", "acceptance": ["Evidence exists"]},
        "expected_outputs": [
            {"path": "workspace/runs/agent-work/1/builder-report.md", "required": True},
        ],
        "validation": {"commands": ["python3 -m json.tool workspace/runs/agent-work/1/story.json"], "risk": "medium"},
    }

    manifest = validation_manifest.build_manifest(story, Path("workspace/runs/agent-work/1/story.json"))
    file_checks = [item for item in manifest["checks"] if item["name"] == "file-exists-builder-report-md"]

    assert file_checks == [
        {
            "name": "file-exists-builder-report-md",
            "type": "file",
            "path": "workspace/runs/agent-work/1/builder-report.md",
            "non_empty": True,
            "required": True,
        }
    ]
