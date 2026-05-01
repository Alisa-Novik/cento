#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
PYTHON_BIN=${PYTHON:-python3}

run_id="dual-backend-stress-$(date +%Y%m%d-%H%M%S)"
run_dir="$ROOT_DIR/workspace/runs/agent-work/$run_id"
cutover_dir="$run_dir/cutover"
log_path="$run_dir/stress.log"
app_log_path="$run_dir/app.log"
db_path="$run_dir/agent-work.sqlite3"

mkdir -p "$cutover_dir"
: > "$log_path"

log() {
  printf '%s\n' "$*" | tee -a "$log_path" >&2
}

run_cmd() {
  log "\$ $*"
  "$@" 2>&1 | tee -a "$log_path"
}

capture_cmd() {
  log "\$ $*"
  "$@" 2> >(tee -a "$log_path" >&2) | tee -a "$log_path"
}

wait_for_api() {
  local attempt
  for attempt in $(seq 1 120); do
    if curl -fsS --max-time 5 "$API_BASE/api/issues?status=open&limit=1" >/dev/null; then
      return 0
    fi
    sleep 0.5
  done
  return 1
}

cleanup() {
  if [[ -n "${reader_list_pid:-}" ]]; then
    kill "$reader_list_pid" 2>/dev/null || true
  fi
  if [[ -n "${reader_detail_pid:-}" ]]; then
    kill "$reader_detail_pid" 2>/dev/null || true
  fi
  if [[ -n "${sync_pid:-}" ]]; then
    kill "$sync_pid" 2>/dev/null || true
  fi
  if [[ -n "${APP_PID:-}" ]]; then
    kill "$APP_PID" 2>/dev/null || true
    wait "$APP_PID" 2>/dev/null || true
  fi
}

trap cleanup EXIT

log "agent-work dual-backend concurrency stress"
log "run dir: $run_dir"
log "log: $log_path"

run_cmd "$PYTHON_BIN" "$ROOT_DIR/scripts/agent_work.py" bootstrap

API_PORT=$("$PYTHON_BIN" - <<'PY'
import socket

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
)
API_BASE="http://127.0.0.1:${API_PORT}"

CENTO_AGENT_WORK_BACKEND=dual \
CENTO_AGENT_WORK_DB="$db_path" \
CENTO_AGENT_WORK_APP_SYNC_SOURCE=disabled \
"$PYTHON_BIN" "$ROOT_DIR/scripts/agent_work_app.py" --host 127.0.0.1 --port "$API_PORT" --sync --db "$db_path" \
  >>"$app_log_path" 2>&1 &
APP_PID=$!

log "replacement app pid: $APP_PID"
log "replacement api: $API_BASE"
log "app log: $app_log_path"

wait_for_api
log "replacement api ready"

builder_agent=${CENTO_STRESS_BUILDER_AGENT:-stress-builder}
validator_agent=${CENTO_STRESS_VALIDATOR_AGENT:-stress-validator}

create_json=$(capture_cmd env \
  CENTO_AGENT_WORK_BACKEND=dual \
  CENTO_AGENT_WORK_DB="$db_path" \
  CENTO_AGENT_WORK_API="$API_BASE" \
  "$PYTHON_BIN" "$ROOT_DIR/scripts/agent_work.py" create \
  --title "Concurrency stress: dual-backend replacement locking" \
  --description "Synthetic issue used to exercise concurrent UI reads, /api/sync, dual-backend create/update/validate, and cutover parity." \
  --node linux \
  --agent "$builder_agent" \
  --role builder \
  --package system-self-improvement \
  --json)

issue_id=$(python3 - "$create_json" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
print(payload["id"])
PY
)

log "synthetic issue id: #$issue_id"

reader_list() {
  local i
  for i in $(seq 1 18); do
    curl -fsS --max-time 10 "$API_BASE/api/issues?status=open&limit=10" >/dev/null
    sleep 0.12
  done
}

reader_detail() {
  local i
  for i in $(seq 1 18); do
    curl -fsS --max-time 10 "$API_BASE/api/issues/$issue_id" >/dev/null
    sleep 0.12
  done
}

sync_loop() {
  local i
  for i in $(seq 1 8); do
    curl -fsS --max-time 30 "$API_BASE/api/sync" >/dev/null
    sleep 0.2
  done
}

reader_list >>"$log_path" 2>&1 &
reader_list_pid=$!
reader_detail >>"$log_path" 2>&1 &
reader_detail_pid=$!
sync_loop >>"$log_path" 2>&1 &
sync_pid=$!

run_cmd env \
  CENTO_AGENT_WORK_BACKEND=dual \
  CENTO_AGENT_WORK_DB="$db_path" \
  CENTO_AGENT_WORK_API="$API_BASE" \
  "$PYTHON_BIN" "$ROOT_DIR/scripts/agent_work.py" update "$issue_id" \
  --status running \
  --note "Concurrency stress update while UI reads and /api/sync run."

run_cmd env \
  CENTO_AGENT_WORK_BACKEND=dual \
  CENTO_AGENT_WORK_DB="$db_path" \
  CENTO_AGENT_WORK_API="$API_BASE" \
  "$PYTHON_BIN" "$ROOT_DIR/scripts/agent_work.py" update "$issue_id" \
  --status validating \
  --note "Concurrency stress validating update while UI reads and /api/sync run."

cat > "$run_dir/validation-report.md" <<EOF
# Validation Evidence

- Issue: #$issue_id
- Purpose: exercise the dual-backend validate path while UI reads and /api/sync run concurrently.
- Result: blocked
- Replacement API: $API_BASE
EOF

set +e
validate_output=$(capture_cmd env \
  CENTO_VALIDATOR_AGENTS="$validator_agent" \
  CENTO_AGENT_WORK_BACKEND=dual \
  CENTO_AGENT_WORK_DB="$db_path" \
  CENTO_AGENT_WORK_API="$API_BASE" \
  "$PYTHON_BIN" "$ROOT_DIR/scripts/agent_work.py" validate "$issue_id" \
  --result blocked \
  --agent "$validator_agent" \
  --node linux \
  --note "Synthetic validation used to exercise the validate path under concurrency.")
validate_rc=$?
set -e
if [[ "$validate_rc" -ne 1 ]]; then
  exit "$validate_rc"
fi
if [[ "$validate_output" != *"validated #$issue_id: BLOCKED -> Blocked"* ]]; then
  log "unexpected validate output:"
  printf '%s\n' "$validate_output" | tee -a "$log_path" >&2
  exit 1
fi

wait "$reader_list_pid"
wait "$reader_detail_pid"
wait "$sync_pid"

log "final /api/sync reconciliation"
curl -fsS --max-time 30 "$API_BASE/api/sync" >>"$log_path" 2>&1

cutover_json=$(capture_cmd env \
  CENTO_AGENT_WORK_BACKEND=dual \
  CENTO_AGENT_WORK_DB="$db_path" \
  CENTO_AGENT_WORK_API="$API_BASE" \
  "$PYTHON_BIN" "$ROOT_DIR/scripts/agent_work.py" cutover-parity \
  --all \
  --include-local \
  --issue "$issue_id" \
  --run-dir "$cutover_dir" \
  --json)

printf '%s\n' "$cutover_json" > "$run_dir/cutover-parity.stdout.json"

status=$(python3 - "$cutover_json" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
print(payload["status"])
PY
)

python3 - "$run_dir" "$issue_id" "$API_BASE" "$db_path" "$log_path" "$app_log_path" "$cutover_dir" "$status" "$builder_agent" "$validator_agent" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

run_dir = Path(sys.argv[1])
issue_id = int(sys.argv[2])
api_base = sys.argv[3]
db_path = sys.argv[4]
log_path = sys.argv[5]
app_log_path = sys.argv[6]
cutover_dir = Path(sys.argv[7])
status = sys.argv[8]
builder_agent = sys.argv[9]
validator_agent = sys.argv[10]

report = {
    "issue_id": issue_id,
    "api_base": api_base,
    "database": db_path,
    "status": status,
    "builder_agent": builder_agent,
    "validator_agent": validator_agent,
    "artifacts": {
        "stress_log": str(log_path),
        "app_log": str(app_log_path),
        "cutover_json": str(cutover_dir / "cutover-parity-report.json"),
        "cutover_md": str(cutover_dir / "cutover-parity-report.md"),
        "validation_report": str(run_dir / "validation-report.md"),
    },
}

(run_dir / "concurrency-stress-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
(run_dir / "concurrency-stress-report.md").write_text(
    "\n".join(
        [
            "# Dual-Backend Concurrency Stress",
            "",
            f"- Issue: #{issue_id}",
            f"- Status: {status.upper()}",
            f"- API: {api_base}",
            f"- Database: {db_path}",
            "",
            "## Evidence",
            f"- Stress log: `{log_path}`",
            f"- Replacement app log: `{app_log_path}`",
            f"- Cutover parity JSON: `{cutover_dir / 'cutover-parity-report.json'}`",
            f"- Cutover parity MD: `{cutover_dir / 'cutover-parity-report.md'}`",
            f"- Validation report: `{run_dir / 'validation-report.md'}`",
        ]
    )
    + "\n",
    encoding="utf-8",
)
PY

log "stress report: $run_dir/concurrency-stress-report.md"
log "stress json: $run_dir/concurrency-stress-report.json"
log "cutover report: $cutover_dir/cutover-parity-report.md"
log "cutover json: $cutover_dir/cutover-parity-report.json"
log "status: ${status^^}"

if [[ "$status" != "pass" ]]; then
  exit 1
fi

log "agent-work dual-backend concurrency stress complete"
