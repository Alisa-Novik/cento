#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from PIL import Image, ImageStat
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
RUNS_ROOT = ROOT / "workspace" / "runs" / "patch-swarm-product-e2e"
VIEWPORTS = [(390, 900), (1365, 1000), (2048, 1000)]

sys.path.insert(0, str(ROOT / "scripts"))
import agent_work_app as app  # noqa: E402
import parallel_delivery as pd  # noqa: E402


class ProductE2EError(RuntimeError):
    pass


def now_id() -> str:
    return datetime.now(timezone.utc).strftime("patch-swarm-product-e2e-%Y%m%dT%H%M%SZ")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def run_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


def init_fixture_repo(path: Path, *, dirty: str = "") -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "README.md").write_text(f"# {path.name}\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=path, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    run_git(path, "add", "README.md")
    subprocess.run(
        ["git", "-c", "user.email=e2e@example.com", "-c", "user.name=Patch Swarm E2E", "commit", "-m", "init"],
        cwd=path,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if dirty == "unprotected":
        (path / "notes.txt").write_text("local notes stay untouched\n", encoding="utf-8")
    elif dirty == "protected":
        (path / ".env").write_text("TOKEN=fixture\n", encoding="utf-8")
    return path


def request_json(method: str, url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=120) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            error_payload = json.loads(body)
        except json.JSONDecodeError:
            error_payload = {"error": body}
        raise ProductE2EError(f"{method} {url} failed: {exc.code} {error_payload}") from exc
    return json.loads(body) if body.strip() else {}


def start_server(db_path: Path) -> tuple[ThreadingHTTPServer, str]:
    with app.connect(db_path) as conn:
        app.init_db(conn)
    server = ThreadingHTTPServer(("127.0.0.1", 0), app.make_handler(db_path))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{server.server_port}"


def png_nonblank(path: Path) -> dict[str, Any]:
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        width, height = image.size
        stat = ImageStat.Stat(rgb)
        extrema = rgb.getextrema()
    return {
        "path": str(path.relative_to(ROOT)),
        "width": width,
        "height": height,
        "stddev_max": max(stat.stddev),
        "extrema": extrema,
        "nonblank": max(stat.stddev) > 1.0,
    }


def capture_screenshots(base_url: str, run_id: str, out_dir: Path) -> list[dict[str, Any]]:
    screenshots: list[dict[str, Any]] = []
    routes = [
        ("index", "/patch-swarm"),
        ("detail", f"/patch-swarm/runs/{run_id}"),
    ]
    screenshot_dir = out_dir / "screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            for route_name, route in routes:
                for width, height in VIEWPORTS:
                    page = browser.new_page(viewport={"width": width, "height": height})
                    console_errors: list[str] = []
                    page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
                    page.goto(f"{base_url}{route}", wait_until="domcontentloaded", timeout=30_000)
                    page.wait_for_selector("#patchSwarmView:not(.hidden)", timeout=20_000)
                    if route_name == "detail":
                        page.wait_for_selector("#patchSwarmEvidence:not(.hidden)", timeout=20_000)
                    page.wait_for_timeout(700)
                    ui_checks = {
                        "fixture_mode_default": page.eval_on_selector("#patchSwarmMode", "el => el.value === 'fixture'"),
                        "start_disabled_empty_task": page.eval_on_selector("#patchSwarmStartButton", "el => el.disabled === true"),
                        "default_repo_is_clean": page.eval_on_selector("#patchSwarmRepoSelect", "el => /aa-clean-app/.test(el.value)"),
                        "no_horizontal_overflow": page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"),
                        "empty_state_correct": page.eval_on_selector(
                            "#patchSwarmDetailEmpty",
                            "(el, routeName) => routeName === 'detail' ? getComputedStyle(el).display === 'none' : getComputedStyle(el).display !== 'none'",
                            route_name,
                        ),
                        "stats_visibility_correct": page.eval_on_selector(
                            "#patchSwarmStats",
                            "(el, routeName) => routeName === 'detail' ? getComputedStyle(el).display !== 'none' : getComputedStyle(el).display === 'none'",
                            route_name,
                        ),
                    }
                    screenshot_path = screenshot_dir / f"{route_name}-{width}x{height}.png"
                    page.screenshot(path=str(screenshot_path), full_page=True)
                    blank_check = png_nonblank(screenshot_path)
                    screenshots.append(
                        {
                            "route": route,
                            "viewport": {"width": width, "height": height},
                            "screenshot": str(screenshot_path.relative_to(ROOT)),
                            "nonblank": blank_check["nonblank"],
                            "blank_check": blank_check,
                            "ui_checks": ui_checks,
                            "console_errors": console_errors,
                        }
                    )
                    page.close()
        finally:
            browser.close()
    return screenshots


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Patch Swarm product release-candidate e2e fixture.")
    parser.add_argument("--run-id", default=now_id())
    args = parser.parse_args()

    run_id = str(args.run_id)
    summary_dir = RUNS_ROOT / run_id
    fixture_root = summary_dir / "repos"
    summary_dir.mkdir(parents=True, exist_ok=True)

    clean_repo = init_fixture_repo(fixture_root / "aa-clean-app")
    dirty_repo = init_fixture_repo(fixture_root / "mm-dirty-app", dirty="unprotected")
    protected_repo = init_fixture_repo(fixture_root / "zz-protected-app", dirty="protected")

    os.environ["CENTO_PATCH_SWARM_REPO_ROOTS"] = str(fixture_root)
    pd.PATCH_SWARM_RUNS_ROOT = summary_dir / "parallel-delivery" / "patch-swarm"
    pd.PIPELINE_ROOT = summary_dir / "dev-pipeline-studio" / "latest"
    pd.FACTORY_RUNS_ROOT = summary_dir / "factory"
    app.PATCH_SWARM_PRODUCT_WORKTREE_ROOT = summary_dir / "product-worktrees"

    server, base_url = start_server(summary_dir / "agent-work-app.sqlite3")
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, detail: str = "") -> None:
        checks.append({"name": name, "status": "passed" if passed else "failed", "detail": detail})

    try:
        repos_payload = request_json("GET", f"{base_url}/api/patch-swarm/repos")
        repos = {item["path"]: item for item in repos_payload.get("repos", []) if isinstance(item, dict)}
        clean_state = repos.get(str(clean_repo.resolve()), {})
        dirty_state = repos.get(str(dirty_repo.resolve()), {})
        protected_state = repos.get(str(protected_repo.resolve()), {})
        check("repo.clean.startable", clean_state.get("can_start") is True and clean_state.get("safety_label") == "clean_startable")
        check("repo.dirty.unprotected_startable", dirty_state.get("can_start") is True and dirty_state.get("safety_label") == "startable_unprotected_dirty")
        check("repo.protected.blocked", protected_state.get("can_start") is False and protected_state.get("protected_dirty_count") == 1)

        blocked = False
        try:
            request_json(
                "POST",
                f"{base_url}/api/patch-swarm/runs",
                {
                    "run_id": f"{run_id}-blocked",
                    "repo_path": str(protected_repo),
                    "task_brief": "This protected dirty repo must not start.",
                    "candidate_target": 10,
                    "mode": "fixture",
                },
            )
        except ProductE2EError as exc:
            blocked = "protected dirty paths" in str(exc)
        check("repo.protected.create_blocked", blocked)

        before_create = app.patch_swarm_repo_snapshot(clean_repo)
        detail = request_json(
            "POST",
            f"{base_url}/api/patch-swarm/runs",
            {
                "run_id": run_id,
                "repo_path": str(clean_repo),
                "task_brief": "Add one local fixture candidate note through Patch Swarm.",
                "candidate_target": 10,
                "max_parallel_agents": 2,
                "providers": "codex-exec,claude-code,api-openai",
                "mode": "fixture",
            },
        )
        after_create = app.patch_swarm_repo_snapshot(clean_repo)
        check("run.kind.product", detail.get("run_kind") == "product" and detail.get("run", {}).get("run_kind") == "product")
        check("run.action_gates.initial", detail.get("action_gates", {}).get("can_approve") is True and detail.get("action_gates", {}).get("can_apply") is False)
        check("run.create.no_selected_repo_mutation", before_create.get("fingerprint") == after_create.get("fingerprint"))
        check("run.create.receipt", detail.get("no_mutation", {}).get("status") == "passed")

        selected_id = str((detail.get("integration", {}).get("selected_candidates") or [""])[0])
        reject_id = str((detail.get("candidates") or [{}])[-1].get("id") or "")
        rejected = request_json("POST", f"{base_url}/api/patch-swarm/runs/{run_id}/reject", {"candidate_ids": [reject_id], "reason": "E2E reject path."})
        check("run.reject.receipt", any(item.get("id") == reject_id and item.get("decision") == "rejected" for item in rejected.get("candidates", [])))

        apply_before_approval_blocked = False
        try:
            request_json("POST", f"{base_url}/api/patch-swarm/runs/{run_id}/apply", {"limit": 1, "use_factory": True})
        except ProductE2EError as exc:
            apply_before_approval_blocked = "approval required" in str(exc)
        check("run.apply.requires_approval", apply_before_approval_blocked)

        approved = request_json("POST", f"{base_url}/api/patch-swarm/runs/{run_id}/approve", {"candidate_ids": [selected_id], "notes": "E2E approval."})
        check("run.approve.receipt", approved.get("approval", {}).get("status") == "approved" and approved.get("action_gates", {}).get("can_apply") is True)

        before_apply = app.patch_swarm_repo_snapshot(clean_repo)
        applied = request_json("POST", f"{base_url}/api/patch-swarm/runs/{run_id}/apply", {"limit": 1, "validate_each": True, "use_factory": True})
        after_apply = app.patch_swarm_repo_snapshot(clean_repo)
        apply_receipt = applied.get("apply_receipt", {})
        worktree = Path(str(apply_receipt.get("worktree") or ""))
        check("run.apply.receipt", apply_receipt.get("status") == "applied" and apply_receipt.get("apply_scope") == "product_worktree_only")
        check("run.apply.product_worktree", str(worktree).startswith(str(app.PATCH_SWARM_PRODUCT_WORKTREE_ROOT)) and worktree.exists())
        check("run.apply.no_selected_repo_mutation", before_apply.get("fingerprint") == after_apply.get("fingerprint") and applied.get("no_mutation", {}).get("status") == "passed")
        check("run.apply.gate_closed", applied.get("action_gates", {}).get("can_apply") is False)

        screenshots = capture_screenshots(base_url, run_id, summary_dir)
        for item in screenshots:
            check(f"screenshot.{item['route']}.{item['viewport']['width']}x{item['viewport']['height']}.nonblank", bool(item.get("nonblank")), item.get("screenshot", ""))
            check(f"screenshot.{item['route']}.{item['viewport']['width']}x{item['viewport']['height']}.no_overflow", bool(item.get("ui_checks", {}).get("no_horizontal_overflow")), item.get("screenshot", ""))
            check(f"screenshot.{item['route']}.{item['viewport']['width']}x{item['viewport']['height']}.empty_state", bool(item.get("ui_checks", {}).get("empty_state_correct")), item.get("screenshot", ""))
            check(f"screenshot.{item['route']}.{item['viewport']['width']}x{item['viewport']['height']}.stats_visibility", bool(item.get("ui_checks", {}).get("stats_visibility_correct")), item.get("screenshot", ""))
            check(f"screenshot.{item['route']}.{item['viewport']['width']}x{item['viewport']['height']}.no_console_errors", not item.get("console_errors"), "; ".join(item.get("console_errors") or []))

        status = "passed" if all(item["status"] == "passed" for item in checks) else "failed"
        summary = {
            "schema_version": "cento.patch_swarm.product_e2e_summary.v1",
            "run_id": run_id,
            "status": status,
            "base_url": base_url,
            "summary_dir": str(summary_dir.relative_to(ROOT)),
            "repos": {
                "clean": str(clean_repo),
                "dirty_unprotected": str(dirty_repo),
                "dirty_protected": str(protected_repo),
            },
            "product_run_dir": str((pd.PATCH_SWARM_RUNS_ROOT / run_id).relative_to(ROOT)),
            "product_worktree_root": str(app.PATCH_SWARM_PRODUCT_WORKTREE_ROOT.relative_to(ROOT)),
            "checks": checks,
            "screenshots": screenshots,
            "written_at": datetime.now(timezone.utc).isoformat(),
        }
        write_json(summary_dir / "summary.json", summary)
        print(json.dumps({"status": status, "run_id": run_id, "summary": str((summary_dir / "summary.json").relative_to(ROOT))}, indent=2))
        return 0 if status == "passed" else 1
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
