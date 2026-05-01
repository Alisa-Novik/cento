#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import story_manifest


ROOT = story_manifest.ROOT

DEFAULT_DESKTOP_VIEWPORT = "1280,1200"
DEFAULT_MOBILE_VIEWPORT = "390,844"


class StoryFormatContext(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def slugify(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", str(value).strip().lower())
    return re.sub(r"-{2,}", "-", text).strip("-") or "screenshot"


def parse_viewport(value: str, fallback: str) -> str:
    raw = str(value or "").strip().replace("x", ",").strip()
    if not raw:
        raw = fallback
    parts = [part.strip() for part in raw.split(",") if part.strip()]
    if len(parts) != 2:
        raise ValueError(f"invalid viewport '{value}'")
    width = int(parts[0])
    height = int(parts[1])
    return f"{width}x{height}"


def normalize_url(raw: str, context: dict[str, str]) -> str:
    url = str(raw).strip()
    if not url:
        return ""
    url = url.format_map(StoryFormatContext(context))
    url = url.replace("file:///{root}/", f"file://{ROOT}/")
    url = url.replace("file://{root}/", f"file://{ROOT}/")
    if url.startswith("file://"):
        return url
    if re.match(r"^[a-z][a-z0-9+.-]*://", url.lower()):
        return url
    path = story_manifest.repo_path(url)
    return f"file://{path}"


def url_available(url: str) -> tuple[bool, str]:
    if not url:
        return False, "missing URL"
    if url.startswith("file://"):
        parsed = urlparse(url)
        path = Path(parsed.path)
        if path.exists():
            return True, str(path)
        return False, f"file not found: {path}"
    if re.match(r"^https?://", url.lower()):
        try:
            with urllib.request.urlopen(url, timeout=8) as response:
                return 200 <= response.status < 400, f"HTTP {response.status}"
        except (urllib.error.URLError, TimeoutError) as exc:
            return False, str(exc)
    return False, f"unsupported URL scheme: {url}"


def extract_output_path(
    run_dir: Path,
    issue_id: str,
    item: dict[str, Any],
) -> Path:
    output = str(item.get("output") or "").strip()
    name = str(item.get("name") or item.get("label") or "screenshot")
    viewport = str(item.get("viewport") or "").strip() or DEFAULT_DESKTOP_VIEWPORT
    dims = parse_viewport(viewport, DEFAULT_DESKTOP_VIEWPORT).replace("x", "x")
    if output:
        return story_manifest.repo_path(output)
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir / "screenshots" / f"issue-{issue_id}-{slugify(name)}-{dims}.png"


def detect_auth(item: dict[str, Any]) -> tuple[str, str]:
    auth = item.get("auth", "none")
    auth_text = str(auth) if isinstance(auth, str) else str(auth.get("mode") if isinstance(auth, dict) else "custom")
    if auth_text.strip().lower() in {"", "none", "{}"}:
        auth_text = "none"
    auth_notes = (
        str(item.get("auth_note") or item.get("token_note") or "")
        .strip()
    )
    if isinstance(auth, dict):
        token_env = str(auth.get("token_env") or auth.get("token_env_var") or "")
        if token_env:
            if auth_notes:
                auth_notes = f"{auth_notes} (env: {token_env})"
            else:
                auth_notes = f"token env: {token_env}"
        if "token" in auth and not auth_notes:
            auth_notes = "token required (masked)"
    if not auth_notes:
        auth_notes = "none"
    return auth_text, auth_notes


def choose_playwright_command() -> list[str]:
    local_bin = ROOT / "node_modules" / ".bin" / "playwright"
    if local_bin.exists():
        return [str(local_bin)]
    if shutil.which("playwright"):
        return [shutil.which("playwright") or ""]
    return ["npx", "--yes", "playwright"]


def route_url_for_item(story: dict[str, Any], item: dict[str, Any], context: dict[str, str]) -> str:
    routes = story.get("routes") or []
    if not isinstance(routes, list) or not routes:
        return ""
    route_name = str(item.get("route") or item.get("route_name") or "").strip().lower()
    if route_name:
        for route in routes:
            if not isinstance(route, dict):
                continue
            if route_name in str(route.get("name") or "").lower():
                return normalize_url(route.get("url", ""), context)
    if len(routes) == 1 and isinstance(routes[0], dict):
        return normalize_url(routes[0].get("url", ""), context)
    return ""


def capture_screenshot(url: str, viewport: str, output: Path, args: argparse.Namespace) -> dict[str, Any]:
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd_base = choose_playwright_command()
    available, availability_message = url_available(url)
    if not available:
        return {
            "ok": False,
            "status": "url_unavailable",
            "message": availability_message,
            "command": shlex.join(cmd_base + ["screenshot"]),
        }
    w, h = parse_viewport(viewport, DEFAULT_DESKTOP_VIEWPORT).split("x")
    cmd = cmd_base + [
        "screenshot",
        "--browser=chromium",
        f"--viewport-size={w},{h}",
        f"--wait-for-timeout={args.wait_ms}",
        url,
        str(output),
    ]
    try:
        proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=args.timeout_seconds)
    except FileNotFoundError as exc:
        return {
            "ok": False,
            "status": "tool_missing",
            "message": f"Playwright unavailable: {exc}",
            "command": shlex.join(cmd),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "status": "timed_out",
            "message": f"Playwright timed out after {args.timeout_seconds}s",
            "command": shlex.join(cmd),
            "stdout": (exc.stdout or ""),
            "stderr": (exc.stderr or ""),
        }
    if proc.returncode == 0 and output.exists() and output.stat().st_size > 0:
        return {
            "ok": True,
            "status": "ok",
            "message": "captured",
            "command": shlex.join(cmd),
            "path": display_path(output),
        }
    return {
        "ok": False,
        "status": "failed",
        "message": f"exit {proc.returncode}: {proc.stderr[-4000:]}",
        "command": shlex.join(cmd),
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-4000:],
    }


def build_targets(story: dict[str, Any], run_dir: Path, context: dict[str, str]) -> list[dict[str, Any]]:
    items = story.get("screenshots") or []
    if not isinstance(items, list):
        raise RuntimeError("story.json screenshots must be a list")
    targets = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("label") or f"screenshot-{index + 1}")
        item_name = name.lower()
        if "desktop" in item_name:
            default_viewport = DEFAULT_DESKTOP_VIEWPORT
        elif "mobile" in item_name:
            default_viewport = DEFAULT_MOBILE_VIEWPORT
        else:
            default_viewport = DEFAULT_MOBILE_VIEWPORT if index else DEFAULT_DESKTOP_VIEWPORT
        viewport = parse_viewport(str(item.get("viewport") or "").strip(), default_viewport)
        output = extract_output_path(run_dir, context["issue"], item)
        url = normalize_url(item.get("url") or "", context)
        if not url:
            url = route_url_for_item(story, item, context)
        auth_mode, auth_notes = detect_auth(item)
        targets.append(
            {
                "name": name,
                "description": str(item.get("description") or "").strip(),
                "url": url,
                "viewport": viewport,
                "output": output,
                "auth_mode": auth_mode,
                "auth_notes": auth_notes,
            }
        )
    return targets


def make_index(path: Path, story_path: Path, story: dict[str, Any], results: list[dict[str, Any]], issue_id: str) -> None:
    lines = [
        f"# Story #{issue_id} Screenshot Evidence",
        "",
        f"Generated: {now_iso()}",
        "",
        f"- Story manifest: `{display_path(story_path)}`",
        f"- Capture source: story.json screenshot requirements",
        "",
        "## Captures",
        "",
        "| Name | URL | Auth | Viewport | Output | Status | Notes |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in results:
        lines.append(
            "| "
            + " | ".join(
                [
                    item["name"],
                    item["url"],
                    f"{item['auth_mode']}: {item['auth_notes']}",
                    item["viewport"],
                    f"`{item['output']}`",
                    "PASS" if item["ok"] else "FAIL",
                    str(item.get("message") or ""),
                ]
            )
            + " |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    story_path = story_manifest.repo_path(args.story_manifest)
    story = story_manifest.load_manifest(story_path)
    issue_id = str((story.get("issue") or {}).get("id") or "unknown")
    context = {
        "root": str(ROOT),
        "issue": issue_id,
        "package": str((story.get("issue") or {}).get("package") or ""),
        "status": str((story.get("issue") or {}).get("status") or ""),
    }
    run_dir = story_manifest.repo_path(args.run_dir or (story.get("paths") or {}).get("run_dir") or str(story_path.parent))
    targets = build_targets(story, run_dir, context)
    if not targets:
        print("No screenshot targets found in story.json", flush=True)
        return 1
    results = []
    for item in targets:
        output = item["output"]
        if output.exists() and not args.force:
            results.append(
                {
                    "name": item["name"],
                    "url": item["url"],
                    "viewport": item["viewport"],
                    "output": display_path(output),
                    "auth_mode": item["auth_mode"],
                    "auth_notes": item["auth_notes"],
                    "ok": True,
                    "status": "skipped",
                    "message": "output exists and --force was not set",
                }
            )
            continue
        capture = capture_screenshot(item["url"], item["viewport"], output, args)
        results.append(
            {
                "name": item["name"],
                "url": item["url"],
                "viewport": item["viewport"],
                "output": display_path(output),
                "auth_mode": item["auth_mode"],
                "auth_notes": item["auth_notes"],
                "ok": bool(capture.get("ok")),
                "status": capture.get("status"),
                "message": capture.get("message"),
                "command": capture.get("command"),
                "stderr": capture.get("stderr", ""),
            }
        )
    pass_count = sum(1 for item in results if item["ok"])
    fail_count = len(results) - pass_count
    metadata = {
        "story_manifest": display_path(story_path),
        "issue_id": issue_id,
        "issue_url": str((story.get("issue") or {}).get("url") or ""),
        "run_dir": display_path(run_dir),
        "generated_at": now_iso(),
        "runner": "python3 scripts/story_screenshot_runner.py",
        "command": " ".join(shlex.quote(part) for part in [os.path.basename(__file__), str(story_path), f"--run-dir={display_path(run_dir)}"]),
        "summary": {
            "total": len(results),
            "pass": pass_count,
            "fail": fail_count,
            "skipped": len([item for item in results if item.get("status") == "skipped"]),
        },
        "evidence": [item for item in results if item.get("ok")],
    }
    metadata_path = story_manifest.repo_path(args.metadata or str(run_dir / "screenshot-evidence.json"))
    index_path = story_manifest.repo_path(args.index or str(run_dir / "screenshot-index.md"))
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    make_index(index_path, story_path, story, results, issue_id)
    print(f"metadata: {display_path(metadata_path)}")
    print(f"index: {display_path(index_path)}")
    for item in results:
        print(f"- {item['name']}: {item['status']} ({item['message']})")
    if fail_count:
        print(f"FAIL: {fail_count}/{len(results)} captures failed", flush=True)
        return 2
    print(f"PASS: {pass_count}/{len(results)} captures", flush=True)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Capture story manifest screenshot evidence with deterministic paths.")
    parser.add_argument("story_manifest", help="Path to the story.json manifest.")
    parser.add_argument("--run-dir", default="", help="Override run directory (defaults to story.paths.run_dir).")
    parser.add_argument("--metadata", default="", help="Override metadata output path (default: <run_dir>/screenshot-evidence.json).")
    parser.add_argument("--index", default="", help="Override markdown index output path (default: <run_dir>/screenshot-index.md).")
    parser.add_argument("--wait-ms", type=int, default=1200, help="Playwright wait-for-timeout in ms.")
    parser.add_argument("--timeout-seconds", type=int, default=60, help="Capture process timeout.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing screenshots.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except Exception as exc:
        print(f"story_screenshot_runner failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
