#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$SCRIPT_DIR/lib/common.sh"

TARGET="."
OUTPUT=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --target)
            TARGET=$2
            shift 2
            ;;
        --output)
            OUTPUT=$2
            shift 2
            ;;
        *)
            cento_die "Unknown argument: $1"
            ;;
    esac
done

TARGET=$(cento_abs_path "$TARGET")
[[ -d "$TARGET" ]] || cento_die "Target directory does not exist: $TARGET"

ROOT=$(cento_repo_root)
RUN_DIR="$ROOT/workspace/runs"
cento_ensure_dir "$RUN_DIR"

if [[ -z "$OUTPUT" ]]; then
    OUTPUT="$RUN_DIR/repo-snapshot-$(basename "$TARGET")-$(cento_timestamp).md"
fi

{
    printf '# Repo Snapshot\n\n'
    printf -- '- Generated: `%s`\n' "$(date --iso-8601=seconds 2>/dev/null || date)"
    printf -- '- Target: `%s`\n' "$TARGET"
    printf '\n## Tree\n\n```text\n'
    find "$TARGET" -maxdepth 3 -not -path '*/.git*' | sort
    printf '```\n'

    if git -C "$TARGET" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        printf '\n## Git Status\n\n```text\n'
        git -C "$TARGET" status --short
        printf '\n```\n'

        printf '\n## Current Branch\n\n```text\n'
        git -C "$TARGET" branch --show-current
        printf '\n```\n'

        printf '\n## Diffstat\n\n```text\n'
        git -C "$TARGET" diff --stat
        git -C "$TARGET" diff --cached --stat
        printf '\n```\n'

        printf '\n## Recent Commits\n\n```text\n'
        git -C "$TARGET" log --oneline -n 10
        printf '\n```\n'
    else
        printf '\n## Git\n\nNot a git repository.\n'
    fi
} >"$OUTPUT"

printf '%s\n' "$OUTPUT"
