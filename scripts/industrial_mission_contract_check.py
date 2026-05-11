#!/usr/bin/env python3
from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
FIXTURE_ROOT = SCRIPT_DIR / "fixtures" / "industrial_panel"
SOURCE_ROOT = FIXTURE_ROOT / "mission-sources"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert_true(isinstance(payload, dict), f"{path} must contain a JSON object")
    return payload


def queue_ids(model: dict[str, Any]) -> list[str]:
    return [str(item.get("id") or "") for item in model.get("queue") or []]


def reload_panel(mission_fixture: Path | None = None, receipt_root: Path | None = None):
    if mission_fixture:
        os.environ["CENTO_INDUSTRIAL_MISSION_FIXTURE"] = str(mission_fixture)
    else:
        os.environ.pop("CENTO_INDUSTRIAL_MISSION_FIXTURE", None)
    if receipt_root:
        os.environ["CENTO_INDUSTRIAL_ACTION_RUN_ROOT"] = str(receipt_root)
    else:
        os.environ.pop("CENTO_INDUSTRIAL_ACTION_RUN_ROOT", None)
    import industrial_panel

    return importlib.reload(industrial_panel)


def assert_source_models() -> None:
    import industrial_mission

    busy = industrial_mission.build_mission_model_from_sources(load_json(SOURCE_ROOT / "busy.json"))
    expected = [
        "issue-101",
        "issue-102",
        "issue-103",
        "issue-104",
        "run-untracked-codex-222",
        "cluster-macos",
        "git-dirty",
    ]
    assert_true(queue_ids(busy) == expected, f"busy queue priority mismatch: {queue_ids(busy)}")
    assert_true(busy["stats"]["review"] == 2, f"busy review count mismatch: {busy['stats']}")
    assert_true(busy["stats"]["blocked"] == 1, f"busy blocked count mismatch: {busy['stats']}")
    assert_true(busy["stats"]["manual"] == 1, f"busy manual count mismatch: {busy['stats']}")
    cluster_item = next(item for item in busy["queue"] if item["id"] == "cluster-macos")
    assert_true("heal" not in " ".join(cluster_item["command"]), f"hero cluster command must be diagnostic: {cluster_item}")

    hub_text = json.dumps(busy["hub"]).upper()
    assert_true("CAPTURE" not in hub_text, "hub must not advertise capture")
    assert_true("BLOCK\"" not in hub_text, "hub must not advertise a block action")
    assert_true("DRY RUN" in hub_text, "hub should advertise dry-run")
    assert_true("CONTEXT" in hub_text, "hub should advertise context")

    clean = industrial_mission.build_mission_model_from_sources(load_json(SOURCE_ROOT / "clean.json"))
    assert_true(clean["queue"] == [], f"clean board should not invent queue work: {clean['queue']}")
    assert_true(clean["brief"]["risk"].startswith("low"), f"clean risk should be low: {clean['brief']}")

    degraded = industrial_mission.build_mission_model_from_sources(load_json(SOURCE_ROOT / "degraded-data-source.json"))
    degraded_ids = queue_ids(degraded)
    assert_true(degraded_ids[:2] == ["cluster-macos", "git-dirty"], f"degraded source fallback queue mismatch: {degraded_ids}")
    assert_true("agent-work unavailable" in degraded["brief"]["risk"], f"degraded risk missing source error: {degraded['brief']}")
    assert_true("stale mesh socket" in degraded["context"]["blocker_watch"], f"degraded context missing cluster detail: {degraded['context']}")


def assert_hero_actions_and_context() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        receipt_root = Path(tmp)
        panel = reload_panel(FIXTURE_ROOT / "mission-action-model.json", receipt_root)
        panel.HERO_STATE.update({"selected": 0, "message": "ready", "output": [], "last_key": ""})

        panel.handle_hero_key(panel.HERO_STATE, "d")
        output_text = "\n".join(panel.HERO_STATE["output"])
        assert_true("hero dry-run ok" in output_text, f"dry-run output missing signal: {output_text}")
        receipts = sorted(receipt_root.glob("*.json"))
        assert_true(receipts, "dry-run should write an action receipt")
        dry_receipt = json.loads(receipts[-1].read_text(encoding="utf-8"))
        assert_true(dry_receipt["dry_run"] is True, f"receipt should mark dry_run true: {dry_receipt}")
        assert_true(dry_receipt["selected_item_id"] == "safe-python", f"receipt selected item mismatch: {dry_receipt}")
        assert_true("hero dry-run ok" in "\n".join(dry_receipt["output_tail"]), f"receipt missing dry-run output: {dry_receipt}")

        panel.handle_hero_key(panel.HERO_STATE, "a")
        output_text = "\n".join(panel.HERO_STATE["output"])
        assert_true("hero command ok" in output_text, f"run output missing signal: {output_text}")

        unsafe = {
            "id": "unsafe-shell",
            "source": "fixture",
            "title": "Unsafe shell",
            "group": "TEST",
            "command": ["bash", "-lc", "echo should-not-run"],
            "dry_run_command": ["bash", "-lc", "echo should-not-run"],
        }
        blocked = panel.run_hero_action(unsafe)
        blocked_text = "\n".join(blocked)
        assert_true("BLOCKED:" in blocked_text, f"unsafe command should be blocked: {blocked_text}")
        receipts = sorted(receipt_root.glob("*.json"))
        blocked_receipt = json.loads(receipts[-1].read_text(encoding="utf-8"))
        assert_true(blocked_receipt["status"] == "blocked", f"blocked receipt status mismatch: {blocked_receipt}")
        assert_true(blocked_receipt["exit_code"] == 126, f"blocked receipt exit mismatch: {blocked_receipt}")

    panel = reload_panel(FIXTURE_ROOT / "mission-busy.json", None)
    panel.HERO_STATE.update({"selected": 0, "message": "ready", "output": [], "last_key": ""})
    panel.handle_hero_key(panel.HERO_STATE, "o")
    context_text = "\n".join(panel.HERO_STATE["output"])
    assert_true("Issue #101" in context_text, f"context should include issue detail: {context_text}")
    assert_true("workspace/runs/agent-work/101/validation-report.md" in context_text, f"context should include evidence: {context_text}")
    assert_true("review-drain" in context_text, f"context should include safe command: {context_text}")


def main() -> int:
    assert_source_models()
    assert_hero_actions_and_context()
    print("industrial mission contract check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
