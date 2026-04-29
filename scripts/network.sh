#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$SCRIPT_DIR/lib/common.sh"

usage() {
    cat <<'USAGE'
Usage: cento network [--tui|--web] [args...]

Modes:
  --tui      Open the terminal network monitor
  --web      Open the cluster network web dashboard

Examples:
  cento network --tui
  cento network --web
  cento network --web --open
  cento network --web --port 47882
USAGE
}

main() {
    local mode=${1:---tui}
    if [[ $# -gt 0 ]]; then
        shift
    fi

    case "$mode" in
        --tui|tui)
            exec "$SCRIPT_DIR/network_tui.sh" "$@"
            ;;
        --web|web)
            exec python3 "$SCRIPT_DIR/network_web_server.py" "$@"
            ;;
        help|-h|--help)
            usage
            ;;
        *)
            usage
            cento_die "Unknown network mode: $mode"
            ;;
    esac
}

main "$@"
