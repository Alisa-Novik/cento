#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

state_dir="${XDG_STATE_HOME:-$HOME/.local/state}/cento"
mkdir -p "$state_dir"

exec /usr/bin/python3 scripts/agent_coordinator.py daemon \
  --no-agent \
  --interval-seconds "${CENTO_COORDINATOR_DAEMON_INTERVAL_SECONDS:-120}" \
  --auto-review-limit "${CENTO_COORDINATOR_AUTO_REVIEW_LIMIT:-30}" \
  --auto-requeue-limit "${CENTO_COORDINATOR_AUTO_REQUEUE_LIMIT:-24}" \
  --auto-dispatch-limit "${CENTO_COORDINATOR_AUTO_DISPATCH_LIMIT:-8}" \
  >> "$state_dir/agent-coordinator-daemon.log" 2>&1
