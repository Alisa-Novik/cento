#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)

CENTO_BIN="${CENTO_BIN:-$ROOT_DIR/scripts/cento.sh}"
OUT_ROOT="${CENTO_AGENT_WORK_HYGIENE_DIR:-$ROOT_DIR/workspace/runs/agent-work/reconciliation}"

issue_id=""
apply_fix=0

usage() {
  cat <<USAGE
Usage: $0 [--issue ISSUE_ID] [--out-dir PATH]
       $0 [--issue ISSUE_ID] [--out-dir PATH] [--apply]

Collects a point-in-time reconciliation view of agent run ledgers against live
tmux/process state for evidence and minimal stale-run fix recommendations.
USAGE
}

while (($#)); do
  case "$1" in
    --issue)
      shift
      issue_id="${1:-}"
      ;;
    --out-dir)
      shift
      OUT_ROOT="${1:-$OUT_ROOT}"
      ;;
    --apply)
      apply_fix=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown argument $1" >&2
      usage
      exit 1
      ;;
  esac
  shift
done

if [[ ! -x "$CENTO_BIN" && ! -x "$(command -v cento)" ]]; then
  echo "error: no usable Cento CLI found at CENTO_BIN=$CENTO_BIN" >&2
  exit 1
fi

if [[ -n "$issue_id" && ! "$issue_id" =~ ^[0-9]+$ ]]; then
  echo "error: --issue requires a numeric issue id" >&2
  exit 1
fi

mkdir -p "$OUT_ROOT"
timestamp=$(date +%Y%m%d-%H%M%S)
run_dir="$OUT_ROOT/hygiene-${timestamp}"
mkdir -p "$run_dir"

run_json_path="$run_dir/agent-work-runs.json"
issue_json_path="$run_dir/agent-work-issues.json"
tmux_json_path="$run_dir/tmux-sessions.txt"
process_json_path="$run_dir/process-probe.txt"
report_path="$run_dir/hygiene-report.md"

if [[ -n "$issue_id" ]]; then
  runs_cmd=("$CENTO_BIN" agent-work runs --json --reconcile --issue "$issue_id")
else
  runs_cmd=("$CENTO_BIN" agent-work runs --json --reconcile)
fi

printf 'cmd_runs=%q\n' "${runs_cmd[@]}"
"${runs_cmd[@]}" > "$run_json_path"

if [[ -n "$issue_id" ]]; then
  issue_cmd=("$CENTO_BIN" agent-work show "$issue_id" --json)
else
  issue_cmd=("$CENTO_BIN" agent-work list --all --json)
fi
printf 'cmd_issues=%q\n' "${issue_cmd[@]}"
"${issue_cmd[@]}" > "$issue_json_path"

if command -v tmux >/dev/null 2>&1; then
  tmux list-sessions -F '#{session_name}\t#{session_created}\t#{session_attached}' > "$tmux_json_path" || true
else
  echo "tmux unavailable on this host" > "$tmux_json_path"
fi

ps -eo pid=,ppid=,command= | grep -E '(^|/)(codex|claude|agent_work.py)' | sed -e 's/^[[:space:]]*//' > "$process_json_path" || true

python3 - "$run_json_path" "$issue_json_path" "$tmux_json_path" "$process_json_path" "$issue_id" "$report_path" "$run_dir" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

run_json_path, issue_json_path, tmux_path, process_path, issue_id, report_path, run_dir = sys.argv[1:]

payload = json.loads(Path(run_json_path).read_text(encoding="utf-8"))
runs = payload.get("runs", [])
issue_payload = json.loads(Path(issue_json_path).read_text(encoding="utf-8"))
issue_rows = issue_payload.get("issues")
if issue_rows is None and isinstance(issue_payload.get("issue"), dict):
    issue_rows = [issue_payload["issue"]]
if issue_rows is None and isinstance(issue_payload, dict) and "id" in issue_payload:
    issue_rows = [issue_payload]
if isinstance(issue_rows, dict):
    issue_rows = [issue_rows]
elif not isinstance(issue_rows, list):
    issue_rows = []

selected_issue = issue_id.strip()

def norm(value: object) -> str:
    return str(value or "").strip().lower()

status_counts: dict[str, int] = {}
stale_runs = []
for run in runs:
    status = norm(run.get("status"))
    status_counts[status] = status_counts.get(status, 0) + 1
    if status == "stale":
        stale_runs.append(run)

tmux_lines = [line.strip() for line in Path(tmux_path).read_text(encoding="utf-8").splitlines() if line.strip()]
process_lines = [line.strip() for line in Path(process_path).read_text(encoding="utf-8").splitlines() if line.strip()]

def issue_is_demo(issue: dict[str, object]) -> bool:
    blob = " ".join(
        str(issue.get(key) or "")
        for key in ("subject", "description", "package", "validation_report", "tracker", "agent", "assignee")
    ).lower()
    reasons = []
    patterns = [
        "browser workflow demo",
        "browser workflow",
        "demo issue",
        "demo",
        "test artifact",
        "test issue",
        "fixture",
        "smoke",
        "probe",
        "sample",
    ]
    for pattern in patterns:
        if pattern in blob:
            reasons.append(pattern)
    if "browser-evidence" in blob:
        reasons.append("evidence-path")
    if "browser" in blob and "workflow" in blob:
        reasons.append("browser-workflow")
    return bool(reasons)

demo_issues = [issue for issue in issue_rows if issue_is_demo(issue)]
open_demo_issues = [issue for issue in demo_issues if str(issue.get("status") or "").lower() != "done"]

lines = [
    "# Agent Run Ledger Hygiene Audit",
    "",
    f"Generated: {payload.get('updated_at', '')}",
    f"Run artifact directory: {run_dir}",
    "",
    "## Command sequence",
    "",
    "1) `cento agent-work runs --json --reconcile` (optionally with `--issue`)",
    "2) `tmux list-sessions -F '#{session_name}\\t#{session_created}\\t#{session_attached}'`",
    "3) `ps -eo pid=,ppid=,command= | grep -E '(^|/)(codex|claude|agent_work.py)'`",
    "",
    f"## Scope",
    "",
]
if selected_issue:
    lines.append(f"- issue_id filter: {selected_issue}")
else:
    lines.append("- issue_id filter: none")

lines.extend(
    [
        "- stale reconciliation: enabled (`--reconcile`)",
        f"- runs count: {len(runs)}",
        f"- stale count: {len(stale_runs)}",
        f"- demo/test issues: {len(demo_issues)}",
        f"- open demo/test issues: {len(open_demo_issues)}",
        "",
        "## Status counts",
        "",
    ]
)
for name in sorted(status_counts):
    lines.append(f"- {name or 'unknown'}: {status_counts[name]}")
lines.extend(["", "## Stale run entries", ""])
if stale_runs:
    for run in stale_runs:
        lines.append(
            "- `{run_id}` issue={issue_id} status={status} pid={pid} child_pid={child_pid} tmux_session={tmux_session}".format(
                run_id=run.get("run_id"),
                issue_id=run.get("issue_id"),
                status=run.get("status"),
                pid=run.get("pid"),
                child_pid=run.get("child_pid"),
                tmux_session=run.get("tmux_session"),
            )
        )
else:
    lines.append("- None.")

lines.extend(
    [
        "",
        "## Demo/Test Issues",
        "",
    ]
)
if open_demo_issues:
    for issue in open_demo_issues:
        lines.append(
            "- `#{issue_id}` {subject} status={status} assignee={assignee} package={package}".format(
                issue_id=issue.get("id"),
                subject=issue.get("subject"),
                status=issue.get("status"),
                assignee=issue.get("assignee") or issue.get("agent") or "unassigned",
                package=issue.get("package") or "default",
            )
        )
else:
    lines.append("- None.")

lines.extend(
    [
        "",
        "## Minimal reconciliation fix suggestion",
        "",
    ]
)
if stale_runs:
    lines.append("Minimal fix: `cento agent-work runs --reconcile` now promotes stale runs back to `running` when pid or tmux is alive; only truly dead entries stay stale.")
    lines.append("If a stale entry still looks wrong after reconciliation, update it explicitly with `run-update`.")
    for run in stale_runs:
        lines.append(
            f"- `cento agent-work run-update {run.get('run_id')} --status stale --health stale_no_process --note \"Reconciled: no active tmux/pid\"`"
        )
else:
    lines.append("- No stale runs detected in reconciled snapshot.")

if open_demo_issues:
    lines.append("")
    lines.append("## Demo/Test cleanup")
    lines.append("")
    lines.append("Use `--apply` to close open demo/test issues so they leave the active operator queue.")
    for issue in open_demo_issues:
        lines.append(
            f"- `cento agent-work update {issue.get('id')} --status done --note \"Closed by hygiene: demo/test artifact.\"`"
        )

lines.extend(["", "## Evidence artifacts", ""])
lines.append(f"- runs JSON: `{run_json_path}`")
lines.append(f"- issues JSON: `{issue_json_path}`")
lines.append(f"- tmux sessions: `{tmux_path}`")
lines.append(f"- process probe: `{process_path}`")

Path(report_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
PY

printf 'agent-work-hygiene report: %s\n' "$report_path"
printf 'runs json: %s\n' "$run_json_path"
printf 'issues json: %s\n' "$issue_json_path"
printf 'tmux sessions: %s\n' "$tmux_json_path"
printf 'process probe: %s\n' "$process_json_path"

if [[ "$apply_fix" -eq 1 ]]; then
  mapfile -t demo_issue_ids < <(
    python3 - "$issue_json_path" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

issue_payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
issue_rows = issue_payload.get("issues")
if issue_rows is None and isinstance(issue_payload.get("issue"), dict):
    issue_rows = [issue_payload["issue"]]
if issue_rows is None and isinstance(issue_payload, dict) and "id" in issue_payload:
    issue_rows = [issue_payload]
if isinstance(issue_rows, dict):
    issue_rows = [issue_rows]
elif not isinstance(issue_rows, list):
    issue_rows = []

def issue_is_demo(issue: dict[str, object]) -> bool:
    blob = " ".join(
        str(issue.get(key) or "")
        for key in ("subject", "description", "package", "validation_report", "tracker", "agent", "assignee")
    ).lower()
    for pattern in ("browser workflow demo", "browser workflow", "demo issue", "demo", "test artifact", "test issue", "fixture", "smoke", "probe", "sample"):
        if pattern in blob:
            return True
    return "browser" in blob and "workflow" in blob

for issue in issue_rows:
    if str(issue.get("status") or "").lower() != "done" and issue_is_demo(issue):
        print(issue.get("id"))
PY
  )
  for issue_id in "${demo_issue_ids[@]}"; do
    if [[ -n "$issue_id" ]]; then
      printf 'closing demo/test issue #%s\n' "$issue_id" >&2
      "$CENTO_BIN" agent-work update "$issue_id" --status done --note "Closed by hygiene: demo/test artifact." >/dev/null
    fi
  done
fi
