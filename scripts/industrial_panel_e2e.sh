#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)

render_hero() {
    local columns=$1
    local lines=$2
    cd "$ROOT_DIR"
    COLUMNS=$columns \
    LINES=$lines \
    CENTO_INDUSTRIAL_HERO_BACKGROUND=1 \
    PYTHONPATH="$SCRIPT_DIR${PYTHONPATH:+:$PYTHONPATH}" \
    python3 "$SCRIPT_DIR/industrial_panel.py" hero --once --plain
}

render_actions() {
    local columns=$1
    local lines=$2
    local actions_fixture=${3:-}
    local cluster_fixture=${4:-}
    cd "$ROOT_DIR"
    COLUMNS=$columns \
    LINES=$lines \
    CENTO_INDUSTRIAL_ACTIONS_FIXTURE=${actions_fixture:+$actions_fixture} \
    CENTO_INDUSTRIAL_CLUSTER_FIXTURE=${cluster_fixture:+$cluster_fixture} \
    PYTHONPATH="$SCRIPT_DIR${PYTHONPATH:+:$PYTHONPATH}" \
    python3 "$SCRIPT_DIR/industrial_panel.py" actions --once --plain
}

render_cluster() {
    local columns=$1
    local lines=$2
    local cluster_fixture=${3:-}
    cd "$ROOT_DIR"
    COLUMNS=$columns \
    LINES=$lines \
    CENTO_INDUSTRIAL_CLUSTER_FIXTURE=${cluster_fixture:+$cluster_fixture} \
    PYTHONPATH="$SCRIPT_DIR${PYTHONPATH:+:$PYTHONPATH}" \
    python3 "$SCRIPT_DIR/industrial_panel.py" cluster --once --plain
}

assert_widths() {
    local columns=$1
    python3 - "$columns" <<'PY'
from __future__ import annotations

import sys
import unicodedata

limit = int(sys.argv[1])
payload = sys.stdin.read().splitlines()


def char_width(char: str) -> int:
    codepoint = ord(char)
    if codepoint == 0 or codepoint < 32 or 0x7F <= codepoint < 0xA0:
        return 0
    if unicodedata.combining(char):
        return 0
    if 0xFE00 <= codepoint <= 0xFE0F:
        return 0
    if unicodedata.east_asian_width(char) in {"F", "W"}:
        return 2
    return 1


for number, line in enumerate(payload, 1):
    width = sum(char_width(char) for char in line)
    if width > limit:
        raise SystemExit(f"line {number} is {width} cells, expected <= {limit}: {line}")
PY
}

output=$(render_hero 120 48)
assert_widths 120 <<<"$output"

grep -Fq 'MISSION CONTROL // CENTRAL ACTION PANE' <<<"$output"
grep -Fq 'not a dashboard - an action router for the whole cockpit' <<<"$output"
grep -Fq 'MISSION BRIEF' <<<"$output"
grep -Fq 'ACTIVE WORK QUEUE' <<<"$output"
grep -Fq 'CONTEXT ENGINE' <<<"$output"
grep -Fq 'KEYBOARD / ACTION HUB' <<<"$output"
grep -Fq 'ACTIONS 12 READY' <<<"$output"
grep -Fq 'ACTION › implement action router' <<<"$output"

if grep -Fq '▀' <<<"$output"; then
    printf 'industrial panel e2e failed: hero rendered image blocks\n' >&2
    exit 1
fi

compact_output=$(render_hero 92 38)
assert_widths 92 <<<"$compact_output"
compact_lines=$(wc -l <<<"$compact_output")
if (( compact_lines > 38 )); then
    printf 'industrial panel e2e failed: compact hero uses %s lines\n' "$compact_lines" >&2
    exit 1
fi
grep -Fq 'ACTIVE WORK QUEUE' <<<"$compact_output"
grep -Fq 'CONTEXT ENGINE' <<<"$compact_output"
grep -Fq 'KEYBOARD / ACTION HUB' <<<"$compact_output"

empty_cluster_output=$(render_cluster 100 40 "$SCRIPT_DIR/fixtures/industrial_panel/cluster-empty.json")
assert_widths 100 <<<"$empty_cluster_output"
grep -Fq 'EMPTY' <<<"$empty_cluster_output"
grep -Fq '0/0 nodes online' <<<"$empty_cluster_output"
grep -Fq 'no nodes registered' <<<"$empty_cluster_output"
if grep -Fq 'REMEDIATION' <<<"$empty_cluster_output"; then
    printf 'industrial panel e2e failed: empty cluster should not show remediation\n' >&2
    exit 1
fi

degraded_cluster_output=$(render_cluster 100 44 "$SCRIPT_DIR/fixtures/industrial_panel/cluster-degraded.json")
assert_widths 100 <<<"$degraded_cluster_output"
grep -Fq 'DEGRADED' <<<"$degraded_cluster_output"
grep -Fq 'stale mesh socket' <<<"$degraded_cluster_output"
grep -Fq 'repair stale socket' <<<"$degraded_cluster_output"
grep -Fq 'restore local metrics' <<<"$degraded_cluster_output"
grep -Fq 'refresh companion heartbeat' <<<"$degraded_cluster_output"
grep -Fq 'metrics unavailable: collector unavailable' <<<"$degraded_cluster_output"

unavailable_cluster_output=$(render_cluster 100 44 "$SCRIPT_DIR/fixtures/industrial_panel/cluster-unavailable.json")
assert_widths 100 <<<"$unavailable_cluster_output"
grep -Fq 'UNAVAILABLE' <<<"$unavailable_cluster_output"
grep -Fq 'cluster status command unavailable' <<<"$unavailable_cluster_output"
grep -Fq 'bridge mesh-status unavailable' <<<"$unavailable_cluster_output"
grep -Fq 'inspect relay bridge' <<<"$unavailable_cluster_output"
grep -Fq 'restore local metrics' <<<"$unavailable_cluster_output"
grep -Fq 'metrics unavailable: collector unavailable' <<<"$unavailable_cluster_output"

actions_output=$(render_actions 96 40)
assert_widths 96 <<<"$actions_output"
grep -Fq 'STATUS' <<<"$actions_output"
grep -Fq 'Cluster status' <<<"$actions_output"
grep -Fq 'Cluster nodes' <<<"$actions_output"
grep -Fq 'Repair degraded cluster' <<<"$actions_output"
grep -Fq 'Check iPhone heartbeat' <<<"$actions_output"
grep -Fq 'Reapply Industrial preset' <<<"$actions_output"
grep -Fq 'ACTION DETAILS' <<<"$actions_output"
grep -Fq 'LAST RESULT' <<<"$actions_output"
grep -Fq 'IDLE Cluster status' <<<"$actions_output"
grep -Fq 'No action has run yet.' <<<"$actions_output"
grep -Fq 'Controls:' <<<"$actions_output"
python3 "$SCRIPT_DIR/industrial_panel_actions_contract_check.py"

empty_actions_output=$(render_actions 96 28 "$SCRIPT_DIR/fixtures/industrial_panel/empty_actions.json")
grep -Fq 'No actions configured.' <<<"$empty_actions_output"

empty_cluster_output=$(render_actions 96 40 "" "$SCRIPT_DIR/fixtures/industrial_panel/cluster-empty.json")
grep -Fq 'cluster has no registered nodes' <<<"$empty_cluster_output"
grep -Fq 'UNAVAILABLE' <<<"$empty_cluster_output"

degraded_cluster_output=$(render_actions 96 40 "" "$SCRIPT_DIR/fixtures/industrial_panel/cluster-degraded.json")
grep -Fq 'READY' <<<"$degraded_cluster_output"
grep -Fq 'ACTION DETAILS' <<<"$degraded_cluster_output"

python3 "$SCRIPT_DIR/industrial_activity_contract_check.py"

printf 'industrial panel e2e passed\n'
