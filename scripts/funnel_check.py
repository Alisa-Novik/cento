#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
FUNNEL = ROOT_DIR / "scripts" / "funnel_module.py"


def run(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, str(FUNNEL), *args],
        cwd=ROOT_DIR,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(f"{args} failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}")
    return result


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="cento-funnel-check-") as temp_dir:
        state_path = Path(temp_dir) / "state.json"
        report_path = Path(temp_dir) / "report.md"
        env = os.environ.copy()
        env["CENTO_FUNNEL_DATA"] = str(state_path)

        run(["init"], env)
        state = json.loads(state_path.read_text())
        required = {"sources", "funnels", "leads", "events", "offers", "actions"}
        missing = required - set(state)
        if missing:
            raise AssertionError(f"missing required collections: {sorted(missing)}")

        run(["validate"], env)
        sources = run(["sources"], env).stdout
        if "linkedin-posts" not in sources or "telegram-referrals" not in sources:
            raise AssertionError("seed sources missing from sources output")

        run(
            [
                "event",
                "conversation_started",
                "--source",
                "linkedin-posts",
                "--funnel",
                "career-consulting-discovery",
                "--lead",
                "ada-lovelace-linkedin",
                "--note",
                "Validation check event",
                "--value",
                "125",
            ],
            env,
        )
        state = json.loads(state_path.read_text())
        if not any(event["type"] == "conversation_started" for event in state["events"]):
            raise AssertionError("event command did not append the validation event")

        report = run(["report", "--output", str(report_path), "--quiet"], env).stdout
        if str(report_path) not in report or not report_path.exists():
            raise AssertionError("report command did not write the expected report path")
        if "linkedin-posts" not in report_path.read_text():
            raise AssertionError("report is missing source summary content")

        bad = subprocess.run(
            [sys.executable, str(FUNNEL), "event", "bad_event", "--source", "missing-source"],
            cwd=ROOT_DIR,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if bad.returncode == 0 or "Unknown source" not in bad.stderr:
            raise AssertionError("unknown source edge case did not fail clearly")

    print("funnel_check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
