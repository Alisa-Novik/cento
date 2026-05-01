#!/usr/bin/env python3

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PORT = 47932


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def repo_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else ROOT / path


def wait_health(port: int, timeout: float = 20.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last = ""
    while time.monotonic() < deadline:
        try:
            with urlopen(f"http://127.0.0.1:{port}/health", timeout=1.5) as response:
                payload = json.loads(response.read().decode("utf-8"))
                return payload if isinstance(payload, dict) else {}
        except (OSError, URLError, json.JSONDecodeError) as exc:
            last = str(exc)
        time.sleep(0.25)
    raise RuntimeError(f"Console did not become healthy on port {port}: {last}")


def write_fallback_png(path: Path) -> None:
    # A valid 1x1 PNG keeps artifact contracts deterministic if browser capture is unavailable.
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


def capture(run_dir: Path, port: int) -> dict[str, Any]:
    screenshots = run_dir / "screenshots"
    screenshots.mkdir(parents=True, exist_ok=True)
    overview = screenshots / "factory-overview.png"
    queue = screenshots / "factory-queue.png"
    integration = screenshots / "factory-integration-dry-run.png"
    checks: list[dict[str, Any]] = []
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 980})
            page.goto(f"http://127.0.0.1:{port}/factory", wait_until="networkidle")
            text = page.locator("body").inner_text(timeout=5000)
            text_lower = text.lower()
            for expected in ("Factory", "Factory Runs", run_dir.name, "Safe Integrator", "Merge Readiness", "release candidate"):
                checks.append({"text": expected, "present": expected.lower() in text_lower})
            page.screenshot(path=str(overview), full_page=True)
            page.screenshot(path=str(queue), full_page=True)
            page.screenshot(path=str(integration), full_page=True)
            browser.close()
        method = "playwright"
        ok = all(item["present"] for item in checks) and overview.exists()
    except Exception as exc:
        write_fallback_png(overview)
        write_fallback_png(queue)
        write_fallback_png(integration)
        checks.append({"text": "playwright_capture", "present": False, "error": str(exc)})
        method = "fallback_png"
        ok = False
    return {
        "schema_version": "factory-console-screenshot-validation/v1",
        "run_dir": rel(run_dir),
        "method": method,
        "passed": ok,
        "checks": checks,
        "screenshots": {
            "overview": rel(overview),
            "queue": rel(queue),
            "integration": rel(integration),
        },
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture Factory Console screenshot evidence.")
    parser.add_argument("--run", required=True)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    run_dir = repo_path(args.run)
    proc = subprocess.Popen(
        [sys.executable, "scripts/agent_work_app.py", "serve", "--host", "127.0.0.1", "--port", str(args.port), "--exact-port"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        wait_health(args.port)
        payload = capture(run_dir, args.port)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    (run_dir / "screenshots" / "screenshot-validation.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True) if args.json else rel(run_dir / "screenshots" / "screenshot-validation.json"))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
