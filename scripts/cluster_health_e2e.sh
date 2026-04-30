#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
RUN_DIR="${CENTO_CLUSTER_HEALTH_RUN_DIR:-$ROOT_DIR/workspace/runs/agent-work/30}"
LOG_DIR="$RUN_DIR/logs"

mkdir -p "$LOG_DIR"

run_step() {
    local name=$1
    shift
    local log="$LOG_DIR/$name.log"
    printf '\n== %s ==\n' "$name"
    printf '$'
    printf ' %q' "$@"
    printf '\n'
    "$@" 2>&1 | tee "$log"
}

run_step mesh-status "$ROOT_DIR/scripts/cento.sh" bridge mesh-status
run_step cluster-status "$ROOT_DIR/scripts/cento.sh" cluster status

run_step cluster-exec-quoted \
    "$ROOT_DIR/scripts/cento.sh" cluster exec linux -- \
    'cd /home/alice/projects/cento && printf "remote:%s:%s\n" "$(hostname)" "$(pwd)"'

run_step cluster-exec-argv \
    "$ROOT_DIR/scripts/cento.sh" cluster exec linux -- \
    printf 'argv:%s:%s\n' hello cluster

run_step bridge-to-linux-quoted \
    "$ROOT_DIR/scripts/cento.sh" bridge to-linux -- \
    'cd /home/alice/projects/cento && printf "bridge:%s:%s\n" "$(hostname)" "$(pwd)"'

cat > "$RUN_DIR/summary.md" <<EOF_SUMMARY
# Cluster Health E2E

Generated: $(date -u '+%Y-%m-%dT%H:%M:%SZ')

Validated from macOS:

- bridge mesh status is readable
- cluster status can evaluate Linux reachability
- \`cento cluster exec linux -- 'cd ... && ...'\` handles quoted shell commands
- \`cento cluster exec linux -- printf ...\` handles argv-style commands
- \`cento bridge to-linux -- 'cd ... && ...'\` handles quoted shell commands

Logs:

- \`logs/mesh-status.log\`
- \`logs/cluster-status.log\`
- \`logs/cluster-exec-quoted.log\`
- \`logs/cluster-exec-argv.log\`
- \`logs/bridge-to-linux-quoted.log\`
EOF_SUMMARY

printf '\ncluster health e2e ok: %s\n' "$RUN_DIR"
