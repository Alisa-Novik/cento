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
    run_dir = RUN_ROOT / f"{now.strftime('%Y%m%d-%H%M%S')}-{args.mode_name}-{slugify(args.task)}"
    run_dir.mkdir(parents=True, exist_ok=True)
    validation_tier = args.validation or str(mode_config.get("validation_tier") or "smoke")
    commit_policy = args.commit or str(mode_config.get("commit_policy") or "none")
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
        return 0

    print(f"Cento {args.mode_name} contract created")
    print(f"Run dir: {contract['artifacts']['run_dir']}")
    print(f"Prompt: {contract['artifacts']['prompt']}")
    print(f"Mode: {args.mode_name} · {contract['time_budget_minutes']}m · {validation_tier} · commit {commit_policy}")
    if dirty_unrelated:
        print(f"Dirty unrelated paths preserved: {len(dirty_unrelated)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
