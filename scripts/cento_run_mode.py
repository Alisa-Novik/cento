#!/usr/bin/env python3
"""Create a Cento execution-mode contract for an operator task."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cento_build  # noqa: E402

MODES_PATH = ROOT / ".cento" / "modes.yaml"
RUN_ROOT = ROOT / "workspace" / "runs" / "cento-run"

DEFAULT_MODES: dict[str, dict[str, Any]] = {
    "fast": {
        "time_budget_minutes": 5,
        "validation_tier": "smoke",
        "info_policy": "infer",
        "ask_policy": "blockers_only",
        "commit_policy": "none",
        "push_policy": "none",
        "max_workers": 0,
        "max_files_changed": 3,
        "repair_attempts": 0,
        "risk_acceptance": "medium",
        "behavior": [
            "Patch the visible issue only.",
            "Infer missing details when the choice is reversible.",
            "Skip broad cleanup, refactors, PRs, and full regression.",
        ],
    },
    "standard": {
        "time_budget_minutes": 15,
        "validation_tier": "focused",
        "info_policy": "ask_if_blocked",
        "ask_policy": "one_batch_if_material",
        "commit_policy": "local_commit",
        "push_policy": "optional",
        "max_workers": 2,
        "max_files_changed": 8,
        "repair_attempts": 1,
        "risk_acceptance": "low_medium",
        "behavior": [
            "Make a scoped product-quality patch.",
            "Ask only if the wrong choice would waste work.",
            "Run targeted validation and commit owned paths when clean.",
        ],
    },
    "thorough": {
        "time_budget_minutes": 30,
        "validation_tier": "product",
        "info_policy": "ask_first",
        "ask_policy": "requirements_or_options_first",
        "commit_policy": "local_commit",
        "push_policy": "branch",
        "pr_policy": "draft",
        "max_workers": 4,
        "max_files_changed": None,
        "repair_attempts": 3,
        "risk_acceptance": "low",
        "behavior": [
            "Plan first with options and budget.",
            "Use explicit manifests, workers, and validation evidence.",
            "Push a branch and prepare PR/taskstream evidence when requested.",
        ],
    },
}


def load_modes() -> dict[str, dict[str, Any]]:
    if not MODES_PATH.exists():
        return DEFAULT_MODES
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(MODES_PATH.read_text(encoding="utf-8")) or {}
        modes = data.get("modes") if isinstance(data, dict) else None
        if isinstance(modes, dict):
            return {**DEFAULT_MODES, **modes}
    except Exception:
        return DEFAULT_MODES
    return DEFAULT_MODES


def parse_args(argv: list[str]) -> argparse.Namespace:
    modes = load_modes()
    parser = argparse.ArgumentParser(
        prog="cento run",
        description="Create a Cento fast/standard/thorough execution contract.",
    )
    parser.add_argument("mode_pos", nargs="?", choices=sorted(modes), help="Execution mode.")
    parser.add_argument("--mode", choices=sorted(modes), help="Execution mode.")
    parser.add_argument("--task", required=True, help="Operator task statement.")
    parser.add_argument("--write", action="append", default=[], help="Owned writable path. Repeatable.")
    parser.add_argument("--read", action="append", default=[], help="Relevant read-only path. Repeatable.")
    parser.add_argument("--route", action="append", default=[], help="Target route or URL. Repeatable.")
    parser.add_argument("--validation", help="Override validation tier.")
    parser.add_argument("--commit", help="Override commit policy.")
    parser.add_argument("--time-budget", help="Override time budget, e.g. 5m.")
    parser.add_argument(
        "--local-builder",
        nargs="?",
        const="fixture",
        default=None,
        help="Run one local builder runtime and collect a patch bundle. Optional runtime name; default fixture.",
    )
    parser.add_argument("--runtime-profile", help="Named local builder runtime profile from .cento/runtimes.yaml.")
    parser.add_argument("--manual-builder", action="store_true", help="Write the build prompt but do not launch a local builder.")
    parser.add_argument("--apply", action="store_true", help="Apply an accepted local-builder patch to the operator worktree.")
    parser.add_argument("--worker-timeout", type=int, default=None, help="Local builder timeout in seconds; runtime profiles can provide the default.")
    parser.add_argument("--fixture-case", default="valid", choices=["valid", "unowned", "protected", "delete", "lockfile", "binary"], help="Fixture case for --local-builder fixture.")
    parser.add_argument("--builder-command", help="Command template for --local-builder command.")
    parser.add_argument("--allow-unsafe-command", action="store_true", help="Allow raw shell command runtime without a named profile.")
    parser.add_argument("--allow-dirty-owned", action="store_true", help="Do not block if owned paths are dirty.")
    parser.add_argument("--copy-prompt", action="store_true", help="Copy the generated prompt to the clipboard.")
    parser.add_argument("--print-prompt", action="store_true", help="Print the generated prompt.")
    parser.add_argument("--json", action="store_true", help="Print the contract JSON path/result only.")
    args = parser.parse_args(argv)
    args.mode_name = args.mode or args.mode_pos
    if not args.mode_name:
        parser.error("provide a mode, e.g. `cento run fast --task ...` or `cento run --mode fast --task ...`")
    return args


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug[:48] or "task"


def run_git_status() -> list[str]:
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or "git status failed")
    return [line for line in result.stdout.splitlines() if line.strip()]


def normalize_path(value: str) -> str:
    path = Path(value)
    if path.is_absolute():
        try:
            return str(path.resolve().relative_to(ROOT))
        except ValueError:
            return str(path)
    return str(path)


def status_path(line: str) -> str:
    path = line[3:]
    if " -> " in path:
        path = path.split(" -> ", 1)[1]
    return path.strip()


def path_overlaps(owner: str, changed: str) -> bool:
    owner = owner.rstrip("/")
    changed = changed.rstrip("/")
    return changed == owner or changed.startswith(owner + "/")


def dirty_summary(write_paths: list[str]) -> tuple[list[str], list[str], list[str]]:
    status_lines = run_git_status()
    changed_paths = [status_path(line) for line in status_lines]
    dirty_owned: list[str] = []
    for owner in write_paths:
        dirty_owned.extend(path for path in changed_paths if path_overlaps(owner, path))
    dirty_owned = sorted(set(dirty_owned))
    dirty_unrelated = sorted(path for path in changed_paths if path not in dirty_owned)
    return status_lines, dirty_owned, dirty_unrelated


def parse_minutes(value: str | None, fallback: Any) -> int:
    if value is None:
        try:
            return int(fallback)
        except Exception:
            return 5
    match = re.fullmatch(r"\s*(\d+)\s*(m|min|minutes?)?\s*", value)
    if not match:
        raise SystemExit(f"Invalid --time-budget: {value}")
    return int(match.group(1))


def copy_to_clipboard(text: str) -> bool:
    for command in (["pbcopy"], ["wl-copy"]):
        if shutil.which(command[0]):
            subprocess.run(command, input=text, text=True, check=False)
            return True
    for command in (["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]):
        if shutil.which(command[0]):
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                start_new_session=True,
            )
            assert process.stdin is not None
            process.stdin.write(text)
            process.stdin.close()
            return True
    return False


def prompt_text(contract: dict[str, Any]) -> str:
    mode = contract["mode"]
    policies = contract["policies"]
    write_paths = contract["paths"]["write"] or ["<not specified>"]
    read_paths = contract["paths"]["read"] or ["<infer from owned paths>"]
    routes = contract["routes"] or ["<not specified>"]
    dirty_note = (
        f"{len(contract['dirty']['unrelated_paths'])} unrelated dirty path(s) exist. Preserve them and stage only owned paths."
        if contract["dirty"]["unrelated_paths"]
        else "No unrelated dirty paths detected."
    )
    build = contract["artifacts"].get("build") or {}
    sections = [
        "You are executing inside Cento.",
        "",
        "Task:",
        contract["task"],
        "",
        "Execution contract:",
        f"- Mode: {mode}",
        f"- Time budget: {contract['time_budget_minutes']} minutes",
        f"- Validation tier: {policies['validation_tier']}",
        f"- Info policy: {policies['info_policy']}",
        f"- Ask policy: {policies['ask_policy']}",
        f"- Commit policy: {policies['commit_policy']}",
        f"- Push policy: {policies['push_policy']}",
        f"- Risk acceptance: {policies['risk_acceptance']}",
        "",
        "Mode behavior:",
        *[f"- {item}" for item in contract["mode_behavior"]],
        "",
        "Owned write paths:",
        *[f"- {path}" for path in write_paths],
        "",
        "Read context:",
        *[f"- {path}" for path in read_paths],
        "",
        "Target routes / URLs:",
        *[f"- {route}" for route in routes],
        "",
        "Build package:",
        f"- Manifest: {build.get('manifest', '<not created>')}",
        f"- Builder prompt: {build.get('prompt', '<not created>')}",
        f"- Integration receipt: {build.get('integration_receipt', '<not created>')}",
        "",
        "Dirty repo policy:",
        "- Preserve unrelated work.",
        "- Do not use git add -A.",
        "- Stage only owned paths if commit policy permits.",
        f"- {dirty_note}",
        "",
        "Required output:",
        "- changed files",
        f"- validation run according to {policies['validation_tier']}",
        "- assumptions made",
        "- known risks / skipped checks",
        "- commit hash only if commit policy permits",
        "",
    ]
    return "\n".join(sections)


def run_build_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "cento_build.py"), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def create_build_artifacts(args: argparse.Namespace, run_slug: str, validation_tier: str) -> dict[str, Any] | None:
    if not args.write:
        return None
    build_id = f"run_{args.mode_name}_{run_slug}".replace("-", "_")
    build_args = argparse.Namespace(
        task=args.task,
        description=args.task,
        mode=args.mode_name,
        write=args.write,
        read=args.read,
        route=args.route,
        protect=[],
        validation=validation_tier,
        id=build_id,
        allow_dirty_owned=args.allow_dirty_owned,
    )
    manifest = cento_build.create_manifest(build_args)
    build_dir = cento_build.BUILD_ROOT / str(manifest["id"])
    build_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = build_dir / "manifest.json"
    prompt_path = build_dir / "builder.prompt.md"
    cento_build.write_json(manifest_path, manifest)
    prompt_path.write_text(cento_build.render_builder_prompt(manifest), encoding="utf-8")
    cento_build.append_event(build_dir, "build_manifest_created", {"manifest_id": manifest["id"], "source": "cento_run"})
    cento_build.append_event(build_dir, "builder_prompt_created", {"path": cento_build.rel(prompt_path)})
    result = {
        "build_id": manifest["id"],
        "build_dir": cento_build.rel(build_dir),
        "manifest": cento_build.rel(manifest_path),
        "prompt": cento_build.rel(prompt_path),
        "status": "pending",
    }
    local_builder_requested = bool(args.local_builder or args.runtime_profile)
    if args.manual_builder or not local_builder_requested:
        validation_receipt = cento_build.run_validation_receipt(
            manifest,
            build_dir,
            skipped=True,
            reason="manual builder mode; no worker patch collected by cento run",
        )
        current_base = cento_build.git_value(["rev-parse", "HEAD"], "HEAD")
        manifest_base = str((manifest.get("source") or {}).get("base_ref") or "HEAD")
        integration_receipt = {
            "schema_version": cento_build.SCHEMA_INTEGRATION_RECEIPT,
            "manifest_id": manifest["id"],
            "status": "pending",
            "mode": manifest.get("mode"),
            "integration_mode": "run_fast_manifest",
            "patch_bundle": None,
            "patch_path": None,
            "touched_paths": [],
            "checks": [
                {"name": "manifest_created", "status": "passed", "details": cento_build.rel(manifest_path)},
                {"name": "worker_patch_collected", "status": "pending", "details": "manual/no local-builder mode"},
            ],
            "applied": False,
            "dry_run": True,
            "rejections": [],
            "warnings": ["no worker patch collected by cento run"],
            "risk_overrides": ["allow_dirty_owned"] if args.allow_dirty_owned else [],
            "dirty_owned_paths": [],
            "dirty_unrelated_paths": [],
            "base_ref_manifest": manifest_base,
            "base_ref_worker": None,
            "base_ref_current": current_base,
            "base_ref_match": cento_build.base_ref_matches(manifest_base, current_base),
            "worktree_path": None,
            "worktree_removed": None,
            "validation_receipt": cento_build.rel(build_dir / "validation_receipt.json"),
            "written_at": cento_build.now_iso(),
        }
        receipt_path = cento_build.write_integration_receipt(build_dir, integration_receipt)
        cento_build.append_event(build_dir, "integration_receipt_pending", {"status": "pending"})
        cento_build.append_event(build_dir, "run_fast_completed", {"status": "pending", "reason": "no local builder"})
        result.update(
            {
                "integration_receipt": cento_build.rel(receipt_path),
                "validation_receipt": cento_build.rel(build_dir / "validation_receipt.json"),
                "validation_status": validation_receipt["status"],
            }
        )
        return result

    runtime = str(args.local_builder or "command")
    try:
        worker_result = cento_build.run_build_worker(
            manifest_path,
            worker_id="builder_1",
            runtime=runtime,
            use_worktree=True,
            timeout=args.worker_timeout,
            allow_dirty_owned=args.allow_dirty_owned,
            fixture_case=args.fixture_case,
            command_template=args.builder_command,
            runtime_profile_name=args.runtime_profile,
            allow_unsafe_command=args.allow_unsafe_command,
        )
    except cento_build.BuildError as exc:
        cento_build.write_taskstream_evidence(build_dir, manifest, status="blocked", changed_files=[], risk_overrides=[])
        cento_build.append_event(build_dir, "run_fast_completed", {"status": "blocked", "reason": str(exc)})
        result.update({"status": "blocked", "error": str(exc), "taskstream_evidence": cento_build.rel(build_dir / "taskstream_evidence.json")})
        return result

    result.update(
        {
            "worker_artifact": worker_result.get("worker_artifact"),
            "patch_bundle": worker_result.get("patch_bundle"),
            "patch": worker_result.get("patch"),
            "handoff": worker_result.get("handoff"),
            "worker_status": worker_result.get("worker_status"),
            "runtime_profile": worker_result.get("runtime_profile"),
        }
    )
    if worker_result.get("status") != "accepted" or not worker_result.get("patch_bundle"):
        cento_build.write_taskstream_evidence(build_dir, manifest, status="blocked", changed_files=[], risk_overrides=[])
        cento_build.append_event(build_dir, "run_fast_completed", {"status": "blocked", "reason": "worker rejected"})
        result.update({"status": "blocked", "error": "; ".join([str(item) for item in worker_result.get("errors") or []])})
        return result

    integrate_args = [
        "integrate",
        cento_build.rel(manifest_path),
        "--bundle",
        str(worker_result["patch_bundle"]),
        "--worktree",
        "--dry-run",
    ]
    if args.allow_dirty_owned:
        integrate_args.append("--allow-dirty-owned")
    integrate_proc = run_build_cli(integrate_args)
    result["integration_stdout"] = integrate_proc.stdout.strip()
    if integrate_proc.returncode != 0:
        cento_build.write_taskstream_evidence(build_dir, manifest, status="blocked", changed_files=[], risk_overrides=[])
        cento_build.append_event(build_dir, "run_fast_completed", {"status": "blocked", "reason": "integration rejected"})
        result.update(
            {
                "status": "blocked",
                "integration_receipt": cento_build.rel(build_dir / "integration_receipt.json"),
                "validation_receipt": cento_build.rel(build_dir / "validation_receipt.json"),
                "error": integrate_proc.stderr.strip() or "integration rejected",
                "taskstream_evidence": cento_build.rel(build_dir / "taskstream_evidence.json"),
            }
        )
        return result

    result.update(
        {
            "integration_receipt": cento_build.rel(build_dir / "integration_receipt.json"),
            "validation_receipt": cento_build.rel(build_dir / "validation_receipt.json"),
            "status": "accepted",
        }
    )
    if args.apply:
        try:
            apply_receipt = cento_build.apply_build_bundle(
                manifest_path,
                ROOT / str(worker_result["patch_bundle"]),
                build_dir / "integration_receipt.json",
                allow_dirty_owned=args.allow_dirty_owned,
            )
        except cento_build.BuildError as exc:
            cento_build.write_taskstream_evidence(build_dir, manifest, status="blocked", changed_files=[], risk_overrides=[])
            cento_build.append_event(build_dir, "run_fast_completed", {"status": "blocked", "reason": str(exc)})
            result.update({"status": "blocked", "error": str(exc), "taskstream_evidence": cento_build.rel(build_dir / "taskstream_evidence.json")})
            return result
        result.update(
            {
                "apply_receipt": cento_build.rel(build_dir / "apply_receipt.json"),
                "validation_receipt": cento_build.rel(build_dir / "validation_receipt.json"),
                "taskstream_evidence": cento_build.rel(build_dir / "taskstream_evidence.json"),
                "apply_status": apply_receipt.get("status"),
                "validation_status": (cento_build.read_json(build_dir / "validation_receipt.json")).get("status")
                if (build_dir / "validation_receipt.json").exists()
                else None,
                "status": "review" if apply_receipt.get("status") == "applied" else "blocked",
            }
        )
        cento_build.append_event(build_dir, "run_fast_completed", {"status": result["status"], "apply_status": apply_receipt.get("status")})
    else:
        cento_build.write_taskstream_evidence(
            build_dir,
            manifest,
            status="review",
            changed_files=[str(item) for item in worker_result.get("touched_paths") or []],
            risk_overrides=[],
        )
        result["taskstream_evidence"] = cento_build.rel(build_dir / "taskstream_evidence.json")
        cento_build.append_event(build_dir, "run_fast_completed", {"status": "review", "applied": False})
    return result


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    modes = load_modes()
    mode_config = modes[args.mode_name]
    write_paths = [normalize_path(path) for path in args.write]
    read_paths = [normalize_path(path) for path in args.read]
    status_lines, dirty_owned, dirty_unrelated = dirty_summary(write_paths)
    if dirty_owned and not args.allow_dirty_owned:
        print("Blocked: owned path is already dirty.", file=sys.stderr)
        for path in dirty_owned:
            print(f"  {path}", file=sys.stderr)
        print("Use --allow-dirty-owned only if you intentionally want to work with those changes.", file=sys.stderr)
        return 2

    now = datetime.now(timezone.utc)
    run_slug = f"{now.strftime('%Y%m%d-%H%M%S')}-{args.mode_name}-{slugify(args.task)}"
    run_dir = RUN_ROOT / run_slug
    run_dir.mkdir(parents=True, exist_ok=True)
    validation_tier = args.validation or str(mode_config.get("validation_tier") or "smoke")
    commit_policy = args.commit or str(mode_config.get("commit_policy") or "none")
    build_artifacts = create_build_artifacts(args, run_slug, validation_tier)
    contract = {
        "schema": "cento.execution-contract.v1",
        "created_at": now.isoformat(),
        "mode": args.mode_name,
        "task": args.task,
        "time_budget_minutes": parse_minutes(args.time_budget, mode_config.get("time_budget_minutes")),
        "routes": args.route,
        "paths": {
            "write": write_paths,
            "read": read_paths,
        },
        "policies": {
            "validation_tier": validation_tier,
            "info_policy": str(mode_config.get("info_policy") or "infer"),
            "ask_policy": str(mode_config.get("ask_policy") or "blockers_only"),
            "commit_policy": commit_policy,
            "push_policy": str(mode_config.get("push_policy") or "none"),
            "risk_acceptance": str(mode_config.get("risk_acceptance") or "medium"),
            "repair_attempts": mode_config.get("repair_attempts", 0),
            "max_workers": mode_config.get("max_workers", 0),
            "max_files_changed": mode_config.get("max_files_changed"),
        },
        "mode_behavior": list(mode_config.get("behavior") or []),
        "dirty": {
            "status_lines": status_lines,
            "owned_paths": dirty_owned,
            "unrelated_paths": dirty_unrelated,
        },
        "artifacts": {
            "run_dir": str(run_dir.relative_to(ROOT)),
            "contract": str((run_dir / "contract.json").relative_to(ROOT)),
            "prompt": str((run_dir / "prompt.md").relative_to(ROOT)),
            "build": build_artifacts,
        },
    }
    prompt = prompt_text(contract)
    (run_dir / "contract.json").write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (run_dir / "prompt.md").write_text(prompt, encoding="utf-8")
    (run_dir / "dirty-baseline.txt").write_text("\n".join(status_lines) + ("\n" if status_lines else ""), encoding="utf-8")

    if args.copy_prompt and not copy_to_clipboard(prompt):
        print("Clipboard unavailable; prompt was written to disk.", file=sys.stderr)
    if args.print_prompt:
        print(prompt)
        return 0
    if args.json:
        print(json.dumps(contract["artifacts"], indent=2, sort_keys=True))
        return 1 if build_artifacts and build_artifacts.get("status") == "blocked" else 0

    print(f"Cento {args.mode_name} contract created")
    print(f"Run dir: {contract['artifacts']['run_dir']}")
    print(f"Prompt: {contract['artifacts']['prompt']}")
    if build_artifacts:
        print(f"Build manifest: {build_artifacts['manifest']}")
        print(f"Build prompt: {build_artifacts['prompt']}")
        if build_artifacts.get("worker_artifact"):
            print(f"Worker artifact: {build_artifacts['worker_artifact']}")
        if build_artifacts.get("patch_bundle"):
            print(f"Patch bundle: {build_artifacts['patch_bundle']}")
        if build_artifacts.get("integration_receipt"):
            print(f"Integration receipt: {build_artifacts['integration_receipt']}")
        if build_artifacts.get("apply_receipt"):
            print(f"Apply receipt: {build_artifacts['apply_receipt']}")
        if build_artifacts.get("validation_receipt"):
            print(f"Validation receipt: {build_artifacts['validation_receipt']}")
        if build_artifacts.get("taskstream_evidence"):
            print(f"Taskstream evidence: {build_artifacts['taskstream_evidence']}")
        if build_artifacts.get("status") == "review":
            print("Fast task complete: patch applied, validation evidence written, commit not created.")
        elif build_artifacts.get("status") == "blocked":
            print(f"Fast task blocked: {build_artifacts.get('error', 'see receipts')}", file=sys.stderr)
    print(f"Mode: {args.mode_name} · {contract['time_budget_minutes']}m · {validation_tier} · commit {commit_policy}")
    if dirty_unrelated:
        print(f"Dirty unrelated paths preserved: {len(dirty_unrelated)}")
    return 1 if build_artifacts and build_artifacts.get("status") == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
