#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$SCRIPT_DIR/lib/common.sh"

ROOT="."
PATTERN="*"
COMMAND=""
MAX_DEPTH=2
DRY_RUN=0
GIT_ONLY=0
STOP_ON_ERROR=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --root)
            ROOT=$2
            shift 2
            ;;
        --pattern)
            PATTERN=$2
            shift 2
            ;;
        --command)
            COMMAND=$2
            shift 2
            ;;
        --max-depth)
            MAX_DEPTH=$2
            shift 2
            ;;
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        --git-only)
            GIT_ONLY=1
            shift
            ;;
        --stop-on-error)
            STOP_ON_ERROR=1
            shift
            ;;
        *)
            cento_die "Unknown argument: $1"
            ;;
    esac
done

[[ -n "$COMMAND" ]] || cento_die "Usage: $0 --root DIR --pattern GLOB --command '...'"
ROOT=$(cento_abs_path "$ROOT")
[[ -d "$ROOT" ]] || cento_die "Root directory does not exist: $ROOT"

matched=0
failed=0

while IFS= read -r dir; do
    [[ -n "$dir" ]] || continue
    if [[ "$GIT_ONLY" -eq 1 ]] && ! git -C "$dir" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        continue
    fi

    matched=$((matched + 1))
    if [[ "$DRY_RUN" -eq 1 ]]; then
        printf '[DRY] %s :: %s\n' "$dir" "$COMMAND"
        continue
    fi

    printf '[RUN] %s :: %s\n' "$dir" "$COMMAND"
    if ! (cd "$dir" && bash -lc "$COMMAND"); then
        failed=$((failed + 1))
        if [[ "$STOP_ON_ERROR" -eq 1 ]]; then
            cento_die "Command failed in $dir"
        fi
    fi
done < <(find "$ROOT" -maxdepth "$MAX_DEPTH" -mindepth 1 -type d -name "$PATTERN" | sort)

printf 'Matched: %s\n' "$matched"
printf 'Failed: %s\n' "$failed"
