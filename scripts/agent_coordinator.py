#!/usr/bin/env python3

from __future__ import annotations

import argparse
import fcntl
import json
import os
import shutil
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = ROOT / "workspace" / "runs" / "agent-coordinator"
STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "cento"
LOCK_FILE = STATE_DIR / "agent-coordinator.lock"
LOG_FILE = STATE_DIR / "agent-coordinator.log"
CRON_BEGIN = "# >>> cento agent-coordinator >>>"
CRON_END = "# <<< cento agent-coordinator <<<"
DEFAULT_MODEL = os.environ.get("CENTO_COORDINATOR_MODEL", "gpt-5.3-codex-spark")
DEFAULT_FALLBACK_MODELS = ["gpt-5.4-mini", "gpt-5.4", "gpt-5.2"]
CODEX_BINARY_CANDIDATES = [
    (os.path.expanduser("~/.npm-global/bin/codex"), "user-local"),
    (os.path.expanduser("~/bin/codex"), "user-local"),
    (os.path.expanduser("~/.local/bin/codex"), "user-local"),
]


def replacement_issue_link(issue_id: int) -> str:
    base = os.environ.get("CENTO_AGENT_WORK_API", "http://127.0.0.1:47910").rstrip("/")
    if base.endswith("/api"):
        base = base[:-4]
    return f"{base}/issues/{issue_id}"


class CoordinatorError(RuntimeError):
    pass


def now() -> datetime:
    return datetime.now(timezone.utc)


def timestamp() -> str:
    return now().strftime("%Y%m%d-%H%M%S")


def run_command(
    cmd: list[str],
    timeout: int,
    cwd: Path = ROOT,
    input_text: str | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    started = now().isoformat()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            env=env,
            input=input_text,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        return {
            "cmd": cmd,
            "started_at": started,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "cmd": cmd,
            "started_at": started,
            "returncode": None,
            "stdout": exc.stdout if isinstance(exc.stdout, str) else "",
            "stderr": (exc.stderr if isinstance(exc.stderr, str) else "") + f"\ntimeout after {timeout}s",
            "timed_out": True,
        }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def update_latest(run_dir: Path) -> None:
    latest = RUNS_DIR / "latest"
    if latest.exists() or latest.is_symlink():
        if latest.is_dir() and not latest.is_symlink():
            shutil.rmtree(latest)
        else:
            latest.unlink()
    try:
        latest.symlink_to(run_dir.name, target_is_directory=True)
    except OSError:
        shutil.copytree(run_dir, latest)


def agent_work(argv: list[str], timeout: int = 45) -> dict[str, Any]:
    return run_command([sys.executable, str(ROOT / "scripts" / "agent_work.py"), *argv], timeout=timeout)


def agent_work_mutation(issue_id: int, argv: list[str], timeout: int = 60) -> dict[str, Any]:
    env = os.environ.copy()
    env["CENTO_AGENT_WORK_BACKEND"] = "replacement" if issue_id >= 1_000_000 else "dual"
    return run_command([sys.executable, str(ROOT / "scripts" / "agent_work.py"), *argv], timeout=timeout, env=env)


def codex_binary_candidates() -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    seen: set[str] = set()

    env_path = os.environ.get("CENTO_CODEX_BIN", "").strip()
    if env_path:
        resolved = str(Path(env_path).expanduser())
        candidates.append({"path": resolved, "source": "env"})
        seen.add(resolved)

    for path, source in CODEX_BINARY_CANDIDATES:
        resolved = str(Path(path).expanduser())
        if resolved in seen:
            continue
        candidates.append({"path": resolved, "source": source})
        seen.add(resolved)

    which = shutil.which("codex") or ""
    if which and which not in seen:
        candidates.append({"path": which, "source": "path"})

    return candidates


def probe_codex_candidate(candidate: dict[str, str]) -> dict[str, Any]:
    path = candidate["path"]
    source = candidate["source"]
    resolved = Path(path)
    present = resolved.exists()
    executable = resolved.exists() and os.access(resolved, os.X_OK)
    probe: dict[str, Any] = {
        "path": path,
        "source": source,
        "present": present,
        "executable": executable,
        "healthy": False,
        "selected": False,
        "reason": "",
        "probe": None,
    }
    if not present:
        probe["reason"] = "missing"
        return probe
    if not executable:
        probe["reason"] = "not executable"
        return probe
    result = run_command([path, "--help"], timeout=10)
    probe["probe"] = {
        "cmd": result["cmd"],
        "returncode": result["returncode"],
        "timed_out": result["timed_out"],
    }
    if result["returncode"] == 0:
        probe["healthy"] = True
        return probe
    probe["reason"] = failure_reason(result)
    return probe


def resolve_codex_health() -> dict[str, Any]:
    probes = [probe_codex_candidate(candidate) for candidate in codex_binary_candidates()]
    selected: dict[str, Any] | None = None
    for candidate in probes:
        if candidate.get("healthy"):
            selected = candidate
            candidate["selected"] = True
            break

    status = "unhealthy"
    reason = "no working codex binary found"
    if selected:
        selected_index = probes.index(selected)
        broken_priorities = [item for item in probes[:selected_index] if not item.get("healthy")]
        if broken_priorities:
            status = "degraded"
            reason = f"fell back from {len(broken_priorities)} broken codex candidate(s)"
        else:
            status = "healthy"
            reason = "working codex binary found"
    else:
        failing = [item for item in probes if item.get("reason")]
        if failing:
            reasons = sorted({str(item.get("reason") or "unknown") for item in failing})
            reason = ", ".join(reasons)

    return {
        "status": status,
        "reason": reason,
        "selected_binary": str(selected["path"]) if selected else "",
        "selected_source": str(selected["source"]) if selected else "",
        "candidates": probes,
    }


def coordinator_health_markdown(health: dict[str, Any], report_path: Path) -> str:
    lines = [
        "## Coordinator Health",
        "",
        f"- Status: `{health.get('status') or 'unknown'}`",
        f"- Reason: `{health.get('reason') or 'none'}`",
        f"- Report path: `{report_path}`",
        f"- Selected binary: `{health.get('selected_binary') or 'none'}`",
        f"- Selected source: `{health.get('selected_source') or 'none'}`",
        "- Candidate probes:",
    ]
    for candidate in health.get("candidates", []):
        state = "healthy" if candidate.get("healthy") else "broken"
        reason = candidate.get("reason") or "ok"
        probe = candidate.get("probe") or {}
        probe_hint = ""
        if probe:
            probe_hint = f" probe_rc={probe.get('returncode')}"
            if probe.get("timed_out"):
                probe_hint += " timed_out=true"
        lines.append(f"- `{candidate.get('path')}` [{candidate.get('source')}] {state}{probe_hint}: {reason}")
    return "\n".join(lines).rstrip()


def prepend_health_markdown(report_path: Path, health: dict[str, Any]) -> None:
    body = report_path.read_text(encoding="utf-8") if report_path.exists() else ""
    prefix = coordinator_health_markdown(health, report_path)
    report_path.write_text(prefix + "\n\n" + body.lstrip(), encoding="utf-8")


def gather_context(run_dir: Path, timeout: int) -> dict[str, Any]:
    output = run_dir / "context.json"
    result = run_command(
        [
            sys.executable,
            str(ROOT / "scripts" / "gather_context.py"),
            "--json",
            "--no-remote",
            "--output",
            str(output),
            "--timeout",
            "6",
        ],
        timeout=timeout,
    )
    return {"result": result, "path": str(output), "payload": read_json(output, {})}


def collect_state(run_dir: Path, timeout: int) -> dict[str, Any]:
    list_result = agent_work(["list", "--json"], timeout=timeout)
    issues = json.loads(list_result["stdout"]).get("issues", []) if list_result["returncode"] == 0 else []
    all_result = agent_work(["list", "--all", "--json"], timeout=timeout)
    all_issues = json.loads(all_result["stdout"]).get("issues", []) if all_result["returncode"] == 0 else []
    runs_result = agent_work(["runs", "--json", "--active"], timeout=timeout)
    active_runs = json.loads(runs_result["stdout"]).get("runs", []) if runs_result["returncode"] == 0 else []
    state = {
        "generated_at": now().isoformat(),
        "agent_work": {
            "open": {"result": list_result, "issues": issues},
            "all": {"result": all_result, "issues": all_issues},
            "active_runs": {"result": runs_result, "runs": active_runs},
        },
        "git": {
            "status": run_command(["git", "status", "--short", "--branch"], timeout=15),
            "diffstat": run_command(["git", "diff", "--stat"], timeout=15),
            "cached_diffstat": run_command(["git", "diff", "--cached", "--stat"], timeout=15),
            "recent_commits": run_command(["git", "log", "--oneline", "-n", "10"], timeout=15),
        },
        "tools": {
            "platforms": run_command([sys.executable, str(ROOT / "scripts" / "platform_report.py"), "--registry", str(ROOT / "data" / "tools.json")], timeout=20),
        },
    }
    write_json(run_dir / "state.json", state)
    return state


def board_summary(state: dict[str, Any]) -> dict[str, Any]:
    issues = state["agent_work"]["open"]["issues"]
    by_status = Counter(issue.get("status", "unknown") for issue in issues)
    by_package = Counter(issue.get("package", "") or "unpackaged" for issue in issues)
    by_tracker = Counter(issue.get("tracker", "unknown") for issue in issues)
    review = [issue for issue in issues if issue.get("status") == "Review"]
    running = [issue for issue in issues if issue.get("status") == "Running"]
    queued = [issue for issue in issues if issue.get("status") == "Queued"]
    blocked = [issue for issue in issues if issue.get("status") == "Blocked"]
    summary = {
        "open_count": len(issues),
        "status_counts": dict(sorted(by_status.items())),
        "tracker_counts": dict(sorted(by_tracker.items())),
        "package_counts": dict(sorted(by_package.items())),
        "review": review,
        "running": running,
        "queued": queued,
        "blocked": blocked,
        "active_runs": state["agent_work"]["active_runs"]["runs"],
    }
    return summary


def render_prompt(run_dir: Path, summary: dict[str, Any]) -> str:
    return f"""You are the Cento replacement coordinator agent.

Goal:
Gather context, inspect current replacement issue/task state, and produce an operator report that suggests:
- which issues should be reviewed, closed, split, blocked, or dispatched next
- exact `cento agent-work ...` commands to run next
- which builder/validator/docs/coordinator agents should be launched or reassigned
- changes to the development process
- tech debt and dev-process improvements that should become replacement tasks
- the coordinator checklist in `docs/agent-work-coordinator-lane.md`

Constraints:
- Do not edit files, run dispatches, create issues, or mutate the board.
- This is a recommendation pass only.
- Prefer concrete commands over vague advice.
- Call out stale running work, review bottlenecks, untracked active agents, and packages with too much queued work.
- Keep the report concise enough to read during operations.

Valid `cento agent-work` command surface:
- Show an issue: `cento agent-work show ISSUE_ID`
- Claim work: `cento agent-work claim ISSUE_ID --node linux --agent AGENT --role builder|validator|coordinator --note "..."`
- Update work: `cento agent-work update ISSUE_ID --status queued|running|validating|review|blocked|done --role builder|validator|coordinator --note "..."`
- Close verified work with `--status done`; do not use `Closed`.
- Validate work: `cento agent-work validate ISSUE_ID --result pass|fail|blocked --evidence PATH --note "..."`
- Dispatch work: `cento agent-work dispatch ISSUE_ID --node linux|macos --agent AGENT --role builder|validator|coordinator --dry-run`
- List active runs: `cento agent-work runs --json --active`
- Inspect a run: `cento agent-work run-status RUN_ID --json`
- Validate a story contract: `python3 scripts/story_manifest.py validate workspace/runs/agent-work/ISSUE_ID/story.json --check-links`
- Render a hub from a story contract: `python3 scripts/story_manifest.py render-hub workspace/runs/agent-work/ISSUE_ID/story.json --check-links`
- Check notification status: `cento notify status`
- Send a state-change notification: `cento notify iphone "ISSUE_ID moved to Review"`
- There is no `--id` flag for update/show/claim/dispatch, no `--done-ratio` flag, no `list --status` flag, and no built-in `run terminate` command.
- `untracked-*` run IDs come from process scans, not ledger files; do not recommend `run-status` for them. Recommend `cento agent-work runs --json --active` and `ps -fp PID` instead.
- Every dispatch recommendation must include `--dry-run` unless the report explicitly says it is an operator-approved mutation command.
- If recommending risky mutations such as closing or blocking work, phrase them as operator review commands, not automatic changes.

Current board summary:
```json
{json.dumps(summary, indent=2)}
```

Available evidence files:
- `{run_dir / "context.json"}`: local Cento context from `gather_context`
- `{run_dir / "state.json"}`: live `cento agent-work` list, all issues, active runs, git state, and platform report

Write the final answer as Markdown with these sections:
1. Snapshot
2. Immediate Next Commands
3. Agent Dispatch Recommendations
4. Review And Closure Queue
5. Process / Tech Debt
6. Risks / Blockers
"""


def fallback_report(summary: dict[str, Any], state: dict[str, Any], reason: str) -> str:
    lines = [
        "# Agent Coordinator Report",
        "",
        f"Generated: `{now().isoformat()}`",
        f"Mode: heuristic fallback (`{reason}`)",
        "",
        "## Snapshot",
        "",
        f"- Open replacement issues: `{summary['open_count']}`",
        f"- Status counts: `{json.dumps(summary['status_counts'], sort_keys=True)}`",
        f"- Package counts: `{json.dumps(summary['package_counts'], sort_keys=True)}`",
        f"- Active runs: `{len(summary['active_runs'])}`",
        "",
        "## Immediate Next Commands",
        "",
    ]
    for issue in summary["review"][:8]:
        lines.append(f"- Review `#{issue['id']}`: `cento agent-work show {issue['id']}`")
    if not summary["review"]:
        lines.append("- No issues are currently in Review; pick the highest-value Running item and ask for handoff evidence.")
    lines.extend(["", "## Agent Dispatch Recommendations", ""])
    for issue in summary["queued"][:8]:
        role = issue.get("role") or "builder"
        agent = issue.get("agent") or "codex"
        node = issue.get("node") or "linux"
        lines.append(f"- Queue `#{issue['id']}` for `{role}` on `{node}`: `cento agent-work dispatch {issue['id']} --node {node} --agent {agent} --dry-run`")
    lines.extend(["", "## Review And Closure Queue", ""])
    for issue in summary["review"][:8]:
        lines.append(f"- `#{issue['id']}` `{issue.get('package')}` is at `{issue.get('done_ratio')}%`: inspect evidence, then move to Done or Blocked.")
    lines.extend(["", "## Process / Tech Debt", ""])
    if len(summary["active_runs"]) and all(run.get("issue_id") is None for run in summary["active_runs"]):
        lines.append("- Active agents are untracked; prefer launching future work through `cento agent-work dispatch` so reports can tie runs to issues.")
    if summary["package_counts"].get("industrial-panels-v1", 0) > 10:
        lines.append("- `industrial-panels-v1` has a large queue; split coordinator attention by panel and validate one vertical slice before dispatching more builders.")
    if summary["status_counts"].get("Review", 0) >= 5:
        lines.append("- Review is the current bottleneck; run `cento agent-work review-drain --package <package> --dry-run` before starting more queued builder work.")
    lines.extend(["", "## Risks / Blockers", ""])
    if state["agent_work"]["open"]["result"]["returncode"] != 0:
        lines.append("- `cento agent-work list --json` failed; replacement visibility is degraded.")
    else:
        lines.append("- No replacement query failure detected.")
    return "\n".join(lines).rstrip() + "\n"


def parse_validation_report(issue: dict[str, Any]) -> dict[str, Any]:
    raw = str(issue.get("validation_report") or "").strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def validation_report_passed(issue: dict[str, Any]) -> tuple[bool, str]:
    report = parse_validation_report(issue)
    if not report:
        return False, "missing validation_report"
    result = str(report.get("result_after_gate") or report.get("result") or "").strip().lower()
    if result != "pass":
        return False, f"validation result is {result or 'unknown'}"
    failures = report.get("review_gate_failures") or []
    if failures:
        return False, "review gate failures present"
    evidence = report.get("evidence") or []
    if isinstance(evidence, str):
        evidence = [evidence]
    if not evidence:
        return False, "validation evidence missing"
    return True, "validation pass with evidence"


def auto_close_review_items(summary: dict[str, Any], run_dir: Path, *, dry_run: bool, limit: int) -> dict[str, Any]:
    actions: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for issue in summary.get("review", []):
        if len(actions) >= limit:
            break
        try:
            issue_id = int(issue.get("id") or 0)
        except (TypeError, ValueError):
            continue
        ok, reason = validation_report_passed(issue)
        if not ok:
            skipped.append({"id": issue_id, "subject": issue.get("subject"), "reason": reason})
            continue
        note = (
            "Coordinator auto-closed Review item after validator PASS evidence.\n\n"
            f"Coordinator run: {run_dir}\n"
            f"Reason: {reason}\n"
            f"Issue: {replacement_issue_link(issue_id)}"
        )
        record = {
            "id": issue_id,
            "subject": issue.get("subject"),
            "package": issue.get("package"),
            "reason": reason,
            "dry_run": dry_run,
        }
        if not dry_run:
            result = agent_work_mutation(
                issue_id,
                [
                    "update",
                    str(issue_id),
                    "--status",
                    "done",
                    "--role",
                    "coordinator",
                    "--note",
                    note,
                    "--json",
                ],
                timeout=90,
            )
            record["result"] = result
            record["ok"] = result.get("returncode") == 0
        actions.append(record)
    return {"closed": actions, "skipped": skipped}


def active_issue_ids(summary: dict[str, Any]) -> set[int]:
    ids: set[int] = set()
    for run in summary.get("active_runs", []):
        if str(run.get("status") or "") not in {"planned", "launching", "running"}:
            continue
        if not (run.get("pid_alive") or run.get("tmux_alive")):
            continue
        try:
            ids.add(int(run.get("issue_id")))
        except (TypeError, ValueError):
            pass
    return ids


def auto_requeue_stale_model_blocked(summary: dict[str, Any], run_dir: Path, *, dry_run: bool, limit: int) -> dict[str, Any]:
    active_ids = active_issue_ids(summary)
    actions: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for issue in summary.get("blocked", []):
        if len(actions) >= limit:
            break
        try:
            issue_id = int(issue.get("id") or 0)
        except (TypeError, ValueError):
            continue
        dispatch = str(issue.get("dispatch") or "")
        if issue_id in active_ids:
            skipped.append({"id": issue_id, "reason": "active run exists"})
            continue
        if "gpt-5.3-codex-spark" not in dispatch:
            skipped.append({"id": issue_id, "reason": "blocked item was not from old Spark dispatch"})
            continue
        role = str(issue.get("role") or "builder") or "builder"
        note = (
            "Coordinator auto-requeued stale Blocked item from old Spark dispatch.\n\n"
            "Reason: previous dispatch used gpt-5.3-codex-spark, which hit quota/stability limits; "
            "pool now relaunches Codex workers with gpt-5.4-mini.\n"
            f"Coordinator run: {run_dir}\n"
            f"Issue: {replacement_issue_link(issue_id)}"
        )
        record = {
            "id": issue_id,
            "subject": issue.get("subject"),
            "package": issue.get("package"),
            "role": role,
            "dry_run": dry_run,
        }
        if not dry_run:
            result = agent_work_mutation(
                issue_id,
                [
                    "update",
                    str(issue_id),
                    "--status",
                    "queued",
                    "--role",
                    role if role in {"builder", "validator", "coordinator"} else "builder",
                    "--note",
                    note,
                    "--json",
                ],
                timeout=90,
            )
            record["result"] = result
            record["ok"] = result.get("returncode") == 0
        actions.append(record)
    return {"requeued": actions, "skipped": skipped}


def run_pool_kick(*, dry_run: bool, max_launch: int) -> dict[str, Any]:
    command = [
        sys.executable,
        str(ROOT / "scripts" / "agent_pool_kick.py"),
        "--max-launch",
        str(max_launch),
    ]
    if dry_run:
        command.append("--dry-run")
    result = run_command(command, timeout=180)
    payload: dict[str, Any] = {
        "cmd": result.get("cmd"),
        "returncode": result.get("returncode"),
        "stdout": result.get("stdout"),
        "stderr": result.get("stderr"),
        "timed_out": result.get("timed_out"),
    }
    try:
        payload["payload"] = json.loads(str(result.get("stdout") or "{}"))
    except json.JSONDecodeError:
        payload["payload"] = {}
    return payload


def apply_auto_actions(summary: dict[str, Any], run_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    if not args.auto:
        return {"enabled": False, "reason": "auto disabled"}
    review = auto_close_review_items(
        summary,
        run_dir,
        dry_run=args.dry_run_actions,
        limit=max(0, args.auto_review_limit),
    )
    requeue = auto_requeue_stale_model_blocked(
        summary,
        run_dir,
        dry_run=args.dry_run_actions,
        limit=max(0, args.auto_requeue_limit),
    )
    pool = run_pool_kick(dry_run=args.dry_run_actions, max_launch=max(0, args.auto_dispatch_limit))
    payload = {
        "enabled": True,
        "dry_run": bool(args.dry_run_actions),
        "generated_at": now().isoformat(),
        "review": review,
        "requeue": requeue,
        "pool": pool,
    }
    write_json(run_dir / "actions.json", payload)
    return payload


def coordinator_models(primary: str) -> list[str]:
    configured = os.environ.get("CENTO_COORDINATOR_FALLBACK_MODELS", "")
    fallback_models = [item.strip() for item in configured.split(",") if item.strip()] if configured else DEFAULT_FALLBACK_MODELS
    models: list[str] = []
    for candidate in [primary, *fallback_models]:
        if candidate and candidate not in models:
            models.append(candidate)
    return models


def looks_rate_limited(result: dict[str, Any]) -> bool:
    text = f"{result.get('stdout') or ''}\n{result.get('stderr') or ''}".lower()
    return "usage limit" in text or "rate limit" in text or "try again" in text


def failure_reason(result: dict[str, Any]) -> str:
    if looks_rate_limited(result):
        attempts = result.get("attempts") or []
        models = [str(attempt.get("model") or "") for attempt in attempts if attempt.get("model")]
        suffix = f" after trying {', '.join(models)}" if models else ""
        return f"coordinator model usage limit{suffix}"
    stderr = (result.get("stderr") or "").strip()
    stdout = (result.get("stdout") or "").strip()
    text = stderr or stdout or f"codex exit {result.get('returncode')}"
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return (lines[-1] if lines else text)[:500]


def compact_agent_attempt(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "model": result.get("model") or "",
        "returncode": result.get("returncode"),
        "timed_out": bool(result.get("timed_out")),
        "cmd": result.get("cmd") or [],
        "stdout_tail": (result.get("stdout") or "")[-1000:],
        "stderr_tail": (result.get("stderr") or "")[-1000:],
    }


def run_single_coordinator_agent(codex: str, prompt: str, report_path: Path, model: str, timeout: int) -> dict[str, Any]:
    if not codex:
        return {"returncode": 127, "stdout": "", "stderr": "codex command not found", "timed_out": False, "cmd": ["codex"]}
    return run_command(
        [
            codex,
            "exec",
            "--cd",
            str(ROOT),
            "--sandbox",
            "read-only",
            "--model",
            model,
            "--output-last-message",
            str(report_path),
            "-",
        ],
        timeout=timeout,
        input_text=prompt,
    )


def run_coordinator_agent(codex: str, prompt: str, report_path: Path, model: str, timeout: int) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    for candidate_model in coordinator_models(model):
        result = run_single_coordinator_agent(codex, prompt, report_path, candidate_model, timeout)
        result["model"] = candidate_model
        attempts.append(compact_agent_attempt(result))
        if result.get("returncode") == 0 and report_path.exists():
            result["attempts"] = attempts
            result["selected_model"] = candidate_model
            return result
        if not looks_rate_limited(result):
            result["attempts"] = attempts
            result["selected_model"] = candidate_model
            return result
    result = attempts[-1] if attempts else {"returncode": 127, "stdout": "", "stderr": "no coordinator model attempts", "timed_out": False, "cmd": []}
    result["attempts"] = attempts
    result["selected_model"] = ""
    return result


def try_heal_codex() -> dict[str, Any]:
    """Attempt npm reinstall if codex is unhealthy. Returns heal attempt record."""
    npm = shutil.which("npm")
    if not npm:
        return {"attempted": False, "reason": "npm not found"}
    result = run_command([npm, "install", "-g", "@openai/codex@latest"], timeout=120)
    return {
        "attempted": True,
        "npm": npm,
        "returncode": result.get("returncode"),
        "timed_out": result.get("timed_out"),
        "stderr_tail": (result.get("stderr") or "")[-300:],
    }


def maybe_alert_board_task(health: dict[str, Any], report_path: Path) -> dict[str, Any] | None:
    issue_id = os.environ.get("CENTO_COORDINATOR_ALERT_ISSUE", "").strip()
    if not issue_id or health.get("status") == "healthy":
        return None
    issue_link = replacement_issue_link(int(issue_id)) if issue_id.isdigit() else ""
    note = (
        f"Coordinator health {health.get('status')}: {health.get('reason')}. "
        f"Report: {report_path}. "
        f"Selected binary: {health.get('selected_binary') or 'none'}."
    )
    if issue_link:
        note = f"{note} Issue: {issue_link}."
    result = agent_work(
        [
            "update",
            issue_id,
            "--status",
            "blocked",
            "--role",
            "coordinator",
            "--note",
            note,
        ],
        timeout=45,
    )
    result["issue_id"] = issue_id
    result["note"] = note
    return result


def command_run(args: argparse.Namespace) -> int:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    with LOCK_FILE.open("a+", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(f"agent-coordinator already running; lock={LOCK_FILE}")
            return 0

        run_dir = RUNS_DIR / timestamp()
        run_dir.mkdir(parents=True, exist_ok=False)
        context = gather_context(run_dir, timeout=args.collect_timeout)
        state = collect_state(run_dir, timeout=args.collect_timeout)
        summary = board_summary(state)
        write_json(run_dir / "summary.json", summary)
        prompt = render_prompt(run_dir, summary)
        write_text(run_dir / "prompt.md", prompt)

        report_path = run_dir / "report.md"
        health = resolve_codex_health()
        heal_result: dict[str, Any] = {"attempted": False, "reason": "codex already healthy"}
        if health.get("status") == "unhealthy" and not args.no_agent:
            heal_result = try_heal_codex()
            if heal_result.get("returncode") == 0:
                health = resolve_codex_health()
        write_json(run_dir / "health.json", {**health, "heal_attempt": heal_result})
        if args.no_agent:
            agent_result = {"returncode": 0, "stdout": "", "stderr": "agent disabled", "timed_out": False, "cmd": []}
            write_text(report_path, fallback_report(summary, state, "agent disabled"))
            agent_report_ok = False
        elif health.get("status") == "unhealthy":
            agent_result = {"returncode": 127, "stdout": "", "stderr": health.get("reason") or "no working codex binary found", "timed_out": False, "cmd": []}
            write_text(report_path, fallback_report(summary, state, agent_result["stderr"]))
            agent_report_ok = False
        else:
            agent_result = run_coordinator_agent(str(health.get("selected_binary") or ""), prompt, report_path, args.model, args.agent_timeout)
            agent_report_ok = agent_result["returncode"] == 0 and report_path.exists()
            if not agent_report_ok:
                reason = failure_reason(agent_result)
                write_text(report_path, fallback_report(summary, state, reason))

        prepend_health_markdown(report_path, health)
        alert_result = maybe_alert_board_task(health, report_path)
        actions = apply_auto_actions(summary, run_dir, args)

        metadata = {
            "run_dir": str(run_dir),
            "report": str(report_path),
            "generated_at": now().isoformat(),
            "model": args.model,
            "selected_model": agent_result.get("selected_model") or agent_result.get("model") or "",
            "selected_binary": health.get("selected_binary") or "",
            "selected_binary_source": health.get("selected_source") or "",
            "health": health,
            "alert_result": alert_result,
            "actions": actions,
            "report_mode": "agent" if agent_report_ok else "heuristic-fallback",
            "context_result": context["result"],
            "agent_result": agent_result,
            "summary": summary,
        }
        write_json(run_dir / "metadata.json", metadata)
        update_latest(run_dir)
        with LOG_FILE.open("a", encoding="utf-8") as log:
            log.write(
                json.dumps(
                    {
                        "generated_at": metadata["generated_at"],
                        "run_dir": str(run_dir),
                        "report": str(report_path),
                        "agent_returncode": agent_result.get("returncode"),
                        "selected_model": metadata["selected_model"],
                        "selected_binary": metadata["selected_binary"],
                        "health_status": health.get("status"),
                        "report_mode": metadata["report_mode"],
                        "actions_enabled": actions.get("enabled"),
                        "auto_closed": len((actions.get("review") or {}).get("closed") or []) if actions.get("enabled") else 0,
                        "auto_requeued": len((actions.get("requeue") or {}).get("requeued") or []) if actions.get("enabled") else 0,
                        "auto_launched": len(((actions.get("pool") or {}).get("payload") or {}).get("successful_launches") or []) if actions.get("enabled") else 0,
                        "auto_launch_reason": (((actions.get("pool") or {}).get("payload") or {}).get("reason_summary") or {}).get("primary_reason") if actions.get("enabled") else "",
                    }
                )
                + "\n"
            )
        print(report_path)
        return 0


def current_crontab() -> str:
    proc = subprocess.run(["crontab", "-l"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0:
        return ""
    return proc.stdout


def cron_block(interval_minutes: int) -> str:
    if interval_minutes <= 0 or 60 % interval_minutes != 0:
        raise CoordinatorError("--interval-minutes must divide 60, for example 5, 10, 15, 20, 30, or 60")
    minute = "0" if interval_minutes == 60 else f"*/{interval_minutes}"
    timeout_cmd = shutil.which("timeout")
    runner = f"{sys.executable} {ROOT / 'scripts' / 'agent_coordinator.py'} run --no-agent"
    if timeout_cmd:
        runner = f"{timeout_cmd} 25m {runner}"
    command = f"cd {ROOT} && {runner} >> {LOG_FILE} 2>&1"
    return f"{CRON_BEGIN}\n{minute} * * * * {command}\n{CRON_END}\n"


def strip_cron_block(text: str) -> str:
    lines = text.splitlines()
    output: list[str] = []
    skipping = False
    for line in lines:
        if line.strip() == CRON_BEGIN:
            skipping = True
            continue
        if line.strip() == CRON_END:
            skipping = False
            continue
        if not skipping:
            output.append(line)
    return "\n".join(output).rstrip() + ("\n" if output else "")


def install_cron(args: argparse.Namespace) -> int:
    new_block = cron_block(args.interval_minutes)
    current = current_crontab()
    updated = strip_cron_block(current) + ("\n" if strip_cron_block(current).strip() else "") + new_block
    if args.dry_run:
        print(updated, end="")
        return 0
    proc = subprocess.run(["crontab", "-"], input=updated, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0:
        raise CoordinatorError(proc.stderr.strip() or "crontab install failed")
    print(f"installed cron: every {args.interval_minutes} minutes")
    print(f"log: {LOG_FILE}")
    return 0


def uninstall_cron(args: argparse.Namespace) -> int:
    current = current_crontab()
    updated = strip_cron_block(current)
    if args.dry_run:
        print(updated, end="")
        return 0
    proc = subprocess.run(["crontab", "-"], input=updated, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0:
        raise CoordinatorError(proc.stderr.strip() or "crontab uninstall failed")
    print("uninstalled agent-coordinator cron")
    return 0


def command_status(args: argparse.Namespace) -> int:
    latest = RUNS_DIR / "latest"
    crontab_text = current_crontab()
    installed = CRON_BEGIN in crontab_text
    metadata = read_json(latest / "metadata.json", {}) if latest.exists() else {}
    health = read_json(latest / "health.json", {}) if latest.exists() else {}
    payload = {
        "cron_installed": installed,
        "runs_dir": str(RUNS_DIR),
        "latest": str(latest.resolve()) if latest.exists() else "",
        "latest_report": str((latest / "report.md").resolve()) if (latest / "report.md").exists() else "",
        "latest_health": health,
        "selected_binary": metadata.get("selected_binary", ""),
        "log": str(LOG_FILE),
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"cron_installed={installed}")
        print(f"runs_dir={RUNS_DIR}")
        print(f"latest={payload['latest'] or 'none'}")
        print(f"latest_report={payload['latest_report'] or 'none'}")
        print(f"latest_health={health.get('status') if health else 'none'}")
        print(f"selected_binary={payload['selected_binary'] or 'none'}")
        print(f"log={LOG_FILE}")
    return 0


def command_docs(_args: argparse.Namespace) -> int:
    print(
        """# Agent Coordinator

On demand:

```bash
python3 scripts/agent_coordinator.py run
```

Install the recurring actor cron:

```bash
python3 scripts/agent_coordinator.py install-cron --interval-minutes 5
```

Outputs:

- `workspace/runs/agent-coordinator/<timestamp>/report.md`
- `workspace/runs/agent-coordinator/latest/report.md`
- `workspace/runs/agent-coordinator/<timestamp>/health.json`
- `~/.local/state/cento/agent-coordinator.log`

Environment:

- `CENTO_CODEX_BIN` overrides the Codex binary candidate path.
- `CENTO_COORDINATOR_ALERT_ISSUE` updates a board task when coordinator health is degraded or unhealthy.
- Use `--no-auto` to make a run report-only; auto mode is the default.
"""
    )
    return 0


def command_daemon(args: argparse.Namespace) -> int:
    while True:
        run_args = argparse.Namespace(
            model=args.model,
            no_agent=args.no_agent,
            collect_timeout=args.collect_timeout,
            agent_timeout=args.agent_timeout,
            auto=args.auto,
            dry_run_actions=args.dry_run_actions,
            auto_review_limit=args.auto_review_limit,
            auto_requeue_limit=args.auto_requeue_limit,
            auto_dispatch_limit=args.auto_dispatch_limit,
        )
        command_run(run_args)
        time.sleep(max(30, args.interval_seconds))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scheduled replacement coordinator agent for Cento agent-work.")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run one coordinator pass now.")
    run.add_argument("--model", default=DEFAULT_MODEL)
    run.add_argument("--no-agent", action="store_true", help="Use built-in heuristic report generation instead of codex exec.")
    run.add_argument("--no-auto", dest="auto", action="store_false", help="Report only; do not close Review items or dispatch more work.")
    run.add_argument("--dry-run-actions", action="store_true", help="Plan auto actions without mutating the board or dispatching agents.")
    run.add_argument("--auto-review-limit", type=int, default=12, help="Maximum passing Review items to auto-close per pass.")
    run.add_argument("--auto-requeue-limit", type=int, default=12, help="Maximum stale old-model Blocked items to requeue per pass.")
    run.add_argument("--auto-dispatch-limit", type=int, default=8, help="Maximum agents to dispatch per pass.")
    run.add_argument("--collect-timeout", type=int, default=60)
    run.add_argument("--agent-timeout", type=int, default=900)
    run.set_defaults(auto=True)
    run.set_defaults(func=command_run)

    install = sub.add_parser("install-cron", help="Install the recurring cron job.")
    install.add_argument("--interval-minutes", type=int, default=5)
    install.add_argument("--dry-run", action="store_true")
    install.set_defaults(func=install_cron)

    uninstall = sub.add_parser("uninstall-cron", help="Remove the recurring cron job.")
    uninstall.add_argument("--dry-run", action="store_true")
    uninstall.set_defaults(func=uninstall_cron)

    status = sub.add_parser("status", help="Show coordinator cron and latest-run state.")
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=command_status)

    docs = sub.add_parser("docs", help="Print brief usage docs.")
    docs.set_defaults(func=command_docs)

    daemon = sub.add_parser("daemon", help="Run the coordinator actor in a long-lived loop.")
    daemon.add_argument("--model", default=DEFAULT_MODEL)
    daemon.add_argument("--no-agent", action="store_true")
    daemon.add_argument("--no-auto", dest="auto", action="store_false")
    daemon.add_argument("--dry-run-actions", action="store_true")
    daemon.add_argument("--auto-review-limit", type=int, default=12)
    daemon.add_argument("--auto-requeue-limit", type=int, default=12)
    daemon.add_argument("--auto-dispatch-limit", type=int, default=8)
    daemon.add_argument("--collect-timeout", type=int, default=60)
    daemon.add_argument("--agent-timeout", type=int, default=900)
    daemon.add_argument("--interval-seconds", type=int, default=300)
    daemon.set_defaults(auto=True, func=command_daemon)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (CoordinatorError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
