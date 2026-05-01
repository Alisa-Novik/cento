#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN_ROOT = ROOT / "workspace" / "runs" / "agent-work" / "docs-module"


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def find_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_health(port: int, timeout_seconds: float = 20.0) -> None:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urlopen(f"http://127.0.0.1:{port}/health", timeout=1.0) as response:
                if response.status == 200:
                    return
        except Exception as exc:
            last_error = exc
        time.sleep(0.25)
    raise RuntimeError(f"Cento Console did not become healthy on port {port}: {last_error}")


def run_command(command: list[str], *, env: dict[str, str] | None = None) -> None:
    completed = subprocess.run(command, cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if completed.returncode != 0:
        raise RuntimeError(
            "command failed: "
            + " ".join(command)
            + f"\nstdout:\n{completed.stdout[-1200:]}\nstderr:\n{completed.stderr[-1200:]}"
        )


def crop_sections(full_screenshot: Path, output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    image = Image.open(full_screenshot)
    width, height = image.size
    left_width = 296
    right_width = 380
    topbar_height = 76
    content_left = left_width
    content_right = max(content_left + 1, width - right_width)

    boxes = {
        "topbar": (0, 0, width, min(topbar_height, height)),
        "left-nav": (0, topbar_height, min(left_width, width), height),
        "hero": (content_left, topbar_height, content_right, min(240, height)),
        "explore": (content_left, 220, content_right, min(650, height)),
        "updates": (content_left, 635, content_right, min(860, height)),
        "support": (content_left, 845, content_right, min(1050, height)),
        "right-toc": (max(0, width - right_width), topbar_height, width, height),
    }
    outputs: dict[str, str] = {}
    for name, box in boxes.items():
        left, top, right, bottom = box
        if right <= left or bottom <= top:
            raise RuntimeError(f"invalid crop box for {name}: {box} from {width}x{height}")
        target = output_dir / f"{name}.png"
        image.crop(box).save(target)
        outputs[name] = rel(target)
    return outputs


def validate_nonblank(paths: list[Path]) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for path in paths:
        image = Image.open(path).convert("RGB")
        extrema = image.getextrema()
        nonblank = any(low != high for low, high in extrema)
        results.append({"path": rel(path), "width": image.width, "height": image.height, "nonblank": nonblank})
        if not nonblank:
            raise RuntimeError(f"screenshot crop is blank: {path}")
    return results


def write_section_stories(run_dir: Path, section_crops: dict[str, str]) -> Path:
    stories = [
        {
            "id": "DOCS-MOD-001",
            "section": "topbar",
            "title": "Global documentation topbar",
            "acceptance": "Brand, product navigation, Docs active state, review queue link, and New issue action match the screenshot.",
        },
        {
            "id": "DOCS-MOD-002",
            "section": "left-nav",
            "title": "Documentation left navigation",
            "acceptance": "Cento general navigation is expanded by default; Taskstream, Cluster, Consulting, and References are folded by default; help card remains visible.",
        },
        {
            "id": "DOCS-MOD-003",
            "section": "hero",
            "title": "Documentation hero copy",
            "acceptance": "The hero title and introduction copy match the provided screenshot.",
        },
        {
            "id": "DOCS-MOD-004",
            "section": "explore",
            "title": "Explore by area cards",
            "acceptance": "Six documentation cards render in a two-row grid with area names, descriptions, and action arrows.",
        },
        {
            "id": "DOCS-MOD-005",
            "section": "updates",
            "title": "Recent updates list",
            "acceptance": "Five dated recent-update rows match the screenshot content and density.",
        },
        {
            "id": "DOCS-MOD-006",
            "section": "support",
            "title": "Support callout",
            "acceptance": "The support callout includes the question mark icon, support text, and Contact support action.",
        },
        {
            "id": "DOCS-MOD-007",
            "section": "right-toc",
            "title": "On-this-page rail",
            "acceptance": "The right rail lists Explore by area, Recent updates, and Need help with active styling.",
        },
    ]
    for story in stories:
        story["visual_evidence"] = section_crops[story["section"]]
    payload = {
        "schema": "cento.docs-module.stories.v1",
        "epic": {
            "id": "DOCS-MOD-EPIC",
            "title": "Documentation module screenshot parity",
            "package": "docs-module",
        },
        "stories": stories,
    }
    output = run_dir / "stories.json"
    write_json(output, payload)
    md = ["# Documentation Module Epic", "", "## Stories", ""]
    for story in stories:
        md.extend(
            [
                f"### {story['id']}: {story['title']}",
                "",
                f"- Section: `{story['section']}`",
                f"- Acceptance: {story['acceptance']}",
                f"- Visual evidence: `{story['visual_evidence']}`",
                "",
            ]
        )
    (run_dir / "stories.md").write_text("\n".join(md), encoding="utf-8")
    return output


def write_validation_manifest(run_dir: Path, evidence_paths: list[str]) -> Path:
    checks = [
        {"name": "agent-work-app-py-compiles", "type": "command", "cwd": str(ROOT), "command": ["python3", "-m", "py_compile", "scripts/agent_work_app.py"]},
        {"name": "agent-work-js-syntax", "type": "command", "cwd": str(ROOT), "command": ["node", "--check", "templates/agent-work-app/app.js"]},
        {
            "name": "docs-html-contains-title",
            "type": "command",
            "cwd": str(ROOT),
            "command": "python3 - <<'PY'\nfrom pathlib import Path\nhtml = Path('templates/agent-work-app/index.html').read_text(encoding='utf-8')\nrequired = ['<details open>', '<summary>Cento</summary>', '<summary>Taskstream</summary>', 'Tool registry', 'AI optimization', 'Cento Documentation', 'Explore by area', 'Recent updates', \"Can't find what you're looking for?\", 'On this page']\nmissing = [item for item in required if item not in html]\nraise SystemExit(1 if missing else 0)\nPY",
        },
    ]
    for path in evidence_paths:
        check_name = "evidence-" + path.replace("/", "-").replace(".", "-")
        checks.append({"name": check_name, "type": "file_exists", "path": path})
    manifest = {
        "task": "DOCS-MOD-E2E",
        "claim": "Documentation module sections are implemented and screenshot evidence exists for each section.",
        "risk": "medium",
        "decision_requested": "approve",
        "checks": checks,
    }
    output = run_dir / "validation.json"
    write_json(output, manifest)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Documentation module screenshot E2E and crop section evidence.")
    parser.add_argument("--run-dir", default=str(DEFAULT_RUN_ROOT), help="Output directory for screenshots, crops, and manifests.")
    parser.add_argument("--viewport", default="2048,1080", help="Desktop viewport for screenshot capture.")
    parser.add_argument("--mobile-viewport", default="390,1200", help="Mobile viewport for smoke screenshot capture.")
    args = parser.parse_args()

    started = time.perf_counter()
    run_dir = Path(args.run_dir).resolve()
    screenshots = run_dir / "screenshots"
    crops = screenshots / "sections"
    run_dir.mkdir(parents=True, exist_ok=True)
    screenshots.mkdir(parents=True, exist_ok=True)
    port = find_port()
    env = os.environ.copy()
    env["CENTO_AGENT_WORK_DB"] = str(run_dir / "e2e-tracker.sqlite3")

    server = subprocess.Popen(
        [
            "python3",
            "scripts/agent_work_app.py",
            "serve",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--exact-port",
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        wait_for_health(port)
        playwright = shutil.which("playwright")
        if not playwright:
            raise RuntimeError("playwright CLI is required for docs module E2E screenshots")

        full_desktop = screenshots / "docs-module-desktop.png"
        full_mobile = screenshots / "docs-module-mobile.png"
        research_desktop = screenshots / "research-center-desktop.png"
        run_command([playwright, "screenshot", f"--viewport-size={args.viewport}", f"http://127.0.0.1:{port}/docs", str(full_desktop)], env=env)
        run_command([playwright, "screenshot", f"--viewport-size={args.viewport}", f"http://127.0.0.1:{port}/research-center", str(research_desktop)], env=env)
        run_command([playwright, "screenshot", "--full-page", f"--viewport-size={args.mobile_viewport}", f"http://127.0.0.1:{port}/docs", str(full_mobile)], env=env)
        section_crops = crop_sections(full_desktop, crops)
        evidence = [full_desktop, research_desktop, full_mobile, *[ROOT / path for path in section_crops.values()]]
        image_stats = validate_nonblank(evidence)
        stories_path = write_section_stories(run_dir, section_crops)
        evidence_paths = [rel(full_desktop), rel(research_desktop), rel(full_mobile), rel(stories_path), rel(run_dir / "stories.md"), *section_crops.values()]
        validation_manifest = write_validation_manifest(run_dir, evidence_paths)
        summary = {
            "schema": "cento.docs-module.e2e.v1",
            "url": f"http://127.0.0.1:{port}/docs",
            "run_dir": rel(run_dir),
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            "ai_calls_used": 0,
            "estimated_ai_cost": 0,
            "stories": rel(stories_path),
            "validation_manifest": rel(validation_manifest),
            "screenshots": {
                "desktop": rel(full_desktop),
                "research_center": rel(research_desktop),
                "mobile": rel(full_mobile),
                "sections": section_crops,
            },
            "image_stats": image_stats,
        }
        write_json(run_dir / "e2e-summary.json", summary)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
