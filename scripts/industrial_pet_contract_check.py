#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
FIXED_NOW = datetime(2026, 5, 12, 14, 0, 0, tzinfo=timezone.utc)


def run(cmd: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def display_width(value: str) -> int:
    width = 0
    for char in ANSI_RE.sub("", value).rstrip("\n"):
        if unicodedata.combining(char):
            continue
        width += 2 if unicodedata.east_asian_width(char) in {"F", "W"} else 1
    return width


def strip_ansi(value: str) -> str:
    return ANSI_RE.sub("", value)


def fixture_database(path: Path) -> None:
    source = json.loads((ROOT / "data" / "industrial-pet.json").read_text(encoding="utf-8"))
    source["rare_events"] = []
    write_json(path, source)


def base_env(tmp: Path, database: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["XDG_STATE_HOME"] = str(tmp / "xdg-state")
    env["CENTO_INDUSTRIAL_PET_NOW"] = FIXED_NOW.isoformat().replace("+00:00", "Z")
    env["CENTO_INDUSTRIAL_PET_DATABASE"] = str(database)
    return env


def check_first_render(tmp: Path, database: Path) -> None:
    state = tmp / "pet.json"
    result = run(
        [
            "./scripts/industrial_pet_tui.sh",
            "--once",
            "--state",
            str(state),
            "--database",
            str(database),
            "--width",
            "88",
            "--height",
            "24",
        ],
        base_env(tmp, database),
    )
    assert_true(result.returncode == 0, result.stderr or result.stdout)
    upper = result.stdout.upper()
    assert_true("DARTH LOLIPOPUS" in upper, "render missing pet header")
    assert_true("SNACK" in upper and "REST" in upper and "MENACE" in upper and "LOYAL" in upper, "render missing stats")
    assert_true("SITH SNACK" in upper and "TINY MISSION" in upper, "render missing activities")
    assert_true("J/K SELECT" in upper and "ENTER PERFORM" in upper, "render missing controls")
    assert_true("▀" in result.stdout, "render missing terminal portrait pixels")
    assert_true("JOBS DASHBOARD" not in upper, "pet render leaked jobs dashboard text")
    assert_true(not state.exists(), "--once should not create the default temp state")


def check_action_state_scope(tmp: Path, database: Path) -> None:
    state = tmp / "custom" / "darth.json"
    env = base_env(tmp, database)
    result = run(
        ["./scripts/industrial_pet_tui.sh", "--action", "nap", "--state", str(state), "--database", str(database)],
        env,
    )
    assert_true(result.returncode == 0, result.stderr or result.stdout)
    assert_true(state.exists(), "action did not write the explicit state file")
    default_state = Path(env["XDG_STATE_HOME"]) / "cento" / "industrial-os" / "darth-lolipopus.json"
    assert_true(not default_state.exists(), "action wrote the default XDG state despite --state override")
    payload = json.loads(state.read_text(encoding="utf-8"))
    assert_true(payload["selected"] == "nap", "state did not record selected action")
    assert_true(payload["stats"]["energy"] > 68, "nap did not raise energy")
    assert_true(payload["activity_log"][0]["activity"] == "Nap", "activity log missing nap entry")


def check_decay_is_deterministic(tmp: Path, database: Path) -> None:
    state = tmp / "decay.json"
    previous = FIXED_NOW - timedelta(hours=10)
    write_json(
        state,
        {
            "name": "Darth Lolipopus",
            "created_at": (FIXED_NOW - timedelta(days=2)).isoformat().replace("+00:00", "Z"),
            "last_seen": previous.isoformat().replace("+00:00", "Z"),
            "updated_at": previous.isoformat().replace("+00:00", "Z"),
            "stats": {"snack": 100, "energy": 100, "menace": 100, "affection": 100},
            "selected": "tiny_mission",
            "latest_comment": "waiting",
            "mood": "smug",
            "activity_log": [],
            "action_count": 0,
        },
    )
    result = run(
        ["./scripts/industrial_pet_tui.sh", "--action", "tiny_mission", "--state", str(state), "--database", str(database)],
        base_env(tmp, database),
    )
    assert_true(result.returncode == 0, result.stderr or result.stdout)
    payload = json.loads(state.read_text(encoding="utf-8"))
    assert_true(payload["stats"]["snack"] == 54, f"unexpected snack decay: {payload['stats']}")
    assert_true(payload["stats"]["energy"] == 70, f"unexpected energy decay: {payload['stats']}")
    assert_true(payload["stats"]["menace"] == 100, f"unexpected menace clamp: {payload['stats']}")
    assert_true(payload["stats"]["affection"] == 96, f"unexpected affection decay: {payload['stats']}")
    assert_true(payload["last_seen"] == FIXED_NOW.isoformat().replace("+00:00", "Z"), "last_seen was not updated deterministically")


def check_recovery(tmp: Path, database: Path) -> None:
    env = base_env(tmp, database)
    for name, content in {"empty": "", "corrupt": "{not-json\n"}.items():
        state = tmp / f"{name}.json"
        state.write_text(content, encoding="utf-8")
        result = run(
            ["./scripts/industrial_pet_tui.sh", "--once", "--state", str(state), "--database", str(database)],
            env,
        )
        assert_true(result.returncode == 0, result.stderr or result.stdout)
        assert_true("DARTH LOLIPOPUS" in result.stdout.upper(), f"{name} state did not recover to pet render")


def check_narrow_width(tmp: Path, database: Path) -> None:
    result = run(
        [
            "./scripts/industrial_pet_tui.sh",
            "--once",
            "--state",
            str(tmp / "narrow.json"),
            "--database",
            str(database),
            "--width",
            "48",
            "--height",
            "18",
        ],
        base_env(tmp, database),
    )
    assert_true(result.returncode == 0, result.stderr or result.stdout)
    too_wide = [(number, display_width(line), line) for number, line in enumerate(result.stdout.splitlines(), start=1) if display_width(line) > 48]
    assert_true(not too_wide, f"narrow render overflowed: {too_wide[:3]}")


def check_slot_portrait_layout(tmp: Path, database: Path) -> None:
    result = run(
        [
            "./scripts/industrial_pet_tui.sh",
            "--once",
            "--portrait",
            "slot",
            "--state",
            str(tmp / "slot.json"),
            "--database",
            str(database),
            "--width",
            "98",
            "--height",
            "24",
        ],
        base_env(tmp, database),
    )
    assert_true(result.returncode == 0, result.stderr or result.stdout)
    assert_true("▀" not in result.stdout, "slot render should not draw terminal-pixel portrait blocks")
    plain_lines = [strip_ansi(line) for line in result.stdout.splitlines()]
    too_wide = [(number, display_width(line), line) for number, line in enumerate(result.stdout.splitlines(), start=1) if display_width(line) > 98]
    assert_true(not too_wide, f"slot render overflowed: {too_wide[:3]}")
    interesting = [line for line in plain_lines if "DARTH LOLIPOPUS" in line or "ACTIVITIES" in line or "SNACK" in line]
    assert_true(interesting, "slot render missing expected right-column content")
    assert_true(all(line.startswith(" " * 20) for line in interesting[:3]), "slot render did not reserve the left image column")


def check_slot_activities_fit(tmp: Path, database: Path) -> None:
    result = run(
        [
            "./scripts/industrial_pet_tui.sh",
            "--once",
            "--portrait",
            "slot",
            "--state",
            str(tmp / "slot-fit.json"),
            "--database",
            str(database),
            "--width",
            "82",
            "--height",
            "24",
        ],
        base_env(tmp, database),
    )
    assert_true(result.returncode == 0, result.stderr or result.stdout)
    plain_lines = [strip_ansi(line) for line in result.stdout.splitlines()]
    start = next((index for index, line in enumerate(plain_lines) if "ACTIVITIES" in line), None)
    assert_true(start is not None, "slot render missing activities section")
    activity_lines = []
    for line in plain_lines[start + 1 :]:
        if not line.strip():
            break
        activity_lines.append(line)
    assert_true(len(activity_lines) >= 6, "slot render missing activity rows")
    assert_true(not any("..." in line for line in activity_lines), f"slot activity row clipped: {activity_lines}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="cento-industrial-pet-") as tmp_name:
        tmp = Path(tmp_name)
        database = tmp / "industrial-pet.json"
        fixture_database(database)
        check_first_render(tmp, database)
        check_action_state_scope(tmp, database)
        check_decay_is_deterministic(tmp, database)
        check_recovery(tmp, database)
        check_narrow_width(tmp, database)
        check_slot_portrait_layout(tmp, database)
        check_slot_activities_fit(tmp, database)
    print("industrial pet contract check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
