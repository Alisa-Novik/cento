#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$SCRIPT_DIR/lib/common.sh"

ROOT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
TOOLS_JSON="$ROOT_DIR/data/tools.json"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/cento"
ALIASES_FILE="$CONFIG_DIR/aliases.sh"

usage() {
    cat <<'USAGE'
Usage: cento quick-help-fzf [--print]

Open a cross-platform fzf command palette for cento built-ins, tools, and
aliases. Enter runs the selected command. --print prints the selected command
without running it.
USAGE
}

current_platform() {
    case "$(uname -s)" in
        Darwin) printf 'macos\n' ;;
        Linux) printf 'linux\n' ;;
        *) uname -s | tr '[:upper:]' '[:lower:]' ;;
    esac
}

emit_entries() {
    local platform
    platform=$(current_platform)

    python3 - "$TOOLS_JSON" "$platform" "$ALIASES_FILE" <<'PY'
import json
import re
import sys
from pathlib import Path

tools_path = Path(sys.argv[1])
platform = sys.argv[2]
aliases_path = Path(sys.argv[3])

builtins = [
    ("help", "Show cento help", "cento help"),
    ("tools", "List registered tools", "cento tools"),
    ("platforms", "List platform support", "cento platforms"),
    ("aliases", "List configured aliases", "cento aliases"),
    ("conf", "Print alias config path", "cento conf --path"),
    ("docs", "Print CLI docs", "cento docs"),
]
for name, description, command in builtins:
    print(f"builtin\t{name}\t{description}\t{command}")

payload = json.loads(tools_path.read_text())
for tool in sorted(payload.get("tools", []), key=lambda item: item["id"]):
    platforms = tool.get("platforms") or ["linux", "macos"]
    if platform not in platforms:
        continue
    command = f"cento {tool['id']}"
    commands = tool.get("commands") or []
    if commands:
        command = commands[0]
    print(f"tool\t{tool['id']}\t{tool.get('description', '')}\t{command}")

if aliases_path.exists():
    pattern = re.compile(r"^cento_alias\s+(\S+)(?:\s+--description\s+\"([^\"]*)\")?\s+--\s+(.+)$")
    for line in aliases_path.read_text().splitlines():
        match = pattern.match(line.strip())
        if not match:
            continue
        name, description, command = match.groups()
        print(f"alias\t{name}\t{description or ''}\tcento {name}")
PY
}

main() {
    local print_only=0
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --print)
                print_only=1
                shift
                ;;
            -h|--help)
                usage
                return 0
                ;;
            *)
                cento_die "Unknown option: $1"
                ;;
        esac
    done

    cento_require_cmd fzf
    cento_require_cmd python3

    local selection command
    selection=$(
        emit_entries \
            | awk -F '\t' '{ printf "%-8s %-24s %s\t%s\n", $1, $2, $3, $4 }' \
            | fzf --height=80% --layout=reverse --border --prompt='cento> '
    ) || return 0

    command=${selection##*$'\t'}
    if [[ "$print_only" -eq 1 ]]; then
        printf '%s\n' "$command"
        return 0
    fi

    exec bash -lc "$command"
}

main "$@"
