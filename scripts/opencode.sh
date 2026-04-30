#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$SCRIPT_DIR/lib/common.sh"

FORK_DIR="${OPENCODE_FORK_DIR:-$HOME/projects/opencode}"

usage() {
    cat <<'USAGE'
Usage: cento opencode [args...]

Thin wrapper around opencode (Alisa-Novik fork of sst/opencode).
All arguments are forwarded to the opencode binary unchanged.

Fork:    https://github.com/Alisa-Novik/opencode
Binary:  opencode (installed via npm opencode-ai)
Source:  ~/projects/opencode  (git clone of fork)

Commands:
  cento opencode              Start opencode TUI (interactive)
  cento opencode --version    Print installed version
  cento opencode --help       Show upstream help
  cento opencode fork-status  Show fork vs installed binary divergence
USAGE
}

fork_status() {
    printf 'binary      %s\n' "$(command -v opencode 2>/dev/null || printf 'not found')"
    printf 'version     %s\n' "$(opencode --version 2>/dev/null || printf 'unknown')"
    if [[ -d "$FORK_DIR/.git" ]]; then
        printf 'fork        %s\n' "$FORK_DIR"
        printf 'fork-head   %s\n' "$(git -C "$FORK_DIR" rev-parse --short HEAD 2>/dev/null || printf 'unknown')"
        printf 'fork-branch %s\n' "$(git -C "$FORK_DIR" branch --show-current 2>/dev/null || printf 'unknown')"
        printf 'fork-remote %s\n' "$(git -C "$FORK_DIR" remote get-url origin 2>/dev/null || printf 'unknown')"
    else
        printf 'fork        not found at %s\n' "$FORK_DIR"
    fi
}

main() {
    case "${1:-}" in
        -h|--help|help)
            usage
            ;;
        fork-status)
            fork_status
            ;;
        *)
            cento_require_cmd opencode
            exec opencode "$@"
            ;;
    esac
}

main "$@"
