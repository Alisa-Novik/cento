#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$SCRIPT_DIR/lib/common.sh"

QUERY=""
ROOT="."
OUTPUT=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --query)
            QUERY=$2
            shift 2
            ;;
        --root)
            ROOT=$2
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

[[ -n "$QUERY" ]] || cento_die "Usage: $0 --query TERM [--root DIR] [--output FILE]"
ROOT=$(cento_abs_path "$ROOT")
[[ -d "$ROOT" ]] || cento_die "Root directory does not exist: $ROOT"

CENTO_ROOT=$(cento_repo_root)
RUN_DIR="$CENTO_ROOT/workspace/runs"
cento_ensure_dir "$RUN_DIR"

if [[ -z "$OUTPUT" ]]; then
    safe_query=$(printf '%s' "$QUERY" | tr -cs '[:alnum:]' '-')
    OUTPUT="$RUN_DIR/search-report-${safe_query}-$(cento_timestamp).md"
fi

if cento_have_cmd rg; then
    MATCHES=$(rg -n --hidden --glob '!.git' "$QUERY" "$ROOT" || true)
else
    MATCHES=$(grep -RIn --exclude-dir=.git "$QUERY" "$ROOT" || true)
fi

{
    printf '# Search Report\n\n'
    printf -- '- Generated: `%s`\n' "$(date --iso-8601=seconds 2>/dev/null || date)"
    printf -- '- Root: `%s`\n' "$ROOT"
    printf -- '- Query: `%s`\n' "$QUERY"
    printf '\n## Matches\n\n'
    if [[ -n "$MATCHES" ]]; then
        printf '```text\n%s\n```\n' "$MATCHES"
    else
        printf 'No matches found.\n'
    fi
} >"$OUTPUT"

printf '%s\n' "$OUTPUT"
