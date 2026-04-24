#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$SCRIPT_DIR/lib/common.sh"

OUTPUT=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --output)
            OUTPUT=$2
            shift 2
            ;;
        *)
            cento_die "Unknown argument: $1"
            ;;
    esac
done

ROOT=$(cento_repo_root)
RUN_DIR="$ROOT/workspace/runs"
cento_ensure_dir "$RUN_DIR"

if [[ -z "$OUTPUT" ]]; then
    OUTPUT="$RUN_DIR/system-inventory-$(cento_timestamp).md"
fi

HOSTNAME_VALUE=$(hostname 2>/dev/null || printf 'unknown')
UNAME_VALUE=$(uname -a 2>/dev/null || printf 'unknown')
SHELL_VALUE=${SHELL:-unknown}
USER_VALUE=${USER:-unknown}
PWD_VALUE=$(pwd)
PATH_VALUE=${PATH:-}

TOOLS=(bash zsh git rg fd jq python3 node go tmux make)

{
    printf '# System Inventory\n\n'
    printf -- '- Generated: `%s`\n' "$(date --iso-8601=seconds 2>/dev/null || date)"
    printf -- '- Host: `%s`\n' "$HOSTNAME_VALUE"
    printf -- '- User: `%s`\n' "$USER_VALUE"
    printf -- '- Shell: `%s`\n' "$SHELL_VALUE"
    printf -- '- Working directory: `%s`\n' "$PWD_VALUE"
    printf '\n## Platform\n\n'
    printf '```text\n%s\n```\n\n' "$UNAME_VALUE"
    printf '## Tool Availability\n\n'
    for tool in "${TOOLS[@]}"; do
        if cento_have_cmd "$tool"; then
            printf -- '- `%s`: `%s`\n' "$tool" "$(command -v "$tool")"
        else
            printf -- '- `%s`: not found\n' "$tool"
        fi
    done
    printf '\n## PATH\n\n'
    printf '```text\n%s\n```\n\n' "$PATH_VALUE"
    printf '## Repo Tree\n\n'
    printf '```text\n'
    find "$ROOT" -maxdepth 2 -not -path "$ROOT/.git*" | sort
    printf '```\n'
} >"$OUTPUT"

printf '%s\n' "$OUTPUT"
