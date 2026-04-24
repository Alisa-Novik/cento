#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$SCRIPT_DIR/lib/common.sh"

ROOT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
TOOLS_JSON="$ROOT_DIR/data/tools.json"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/cento"
CONFIG_FILE="$CONFIG_DIR/aliases.sh"
CONFIG_TEMPLATE="$ROOT_DIR/templates/cento/aliases.sh"

declare -A CENTO_ALIAS_COMMANDS=()
declare -A CENTO_ALIAS_DESCRIPTIONS=()

usage() {
    cat <<'USAGE'
Usage: cento <command> [args...]

Built-ins:
  help                 Show this help
  tools                List registered cento tools
  aliases              List configured user aliases
  conf [--path]        Open or print the cento config file
  run TOOL [args...]   Run a registered tool by id

Routing:
  cento TOOL [args...]    Run a registered tool directly
  cento ALIAS [args...]   Run a configured alias directly

Examples:
  cento tools
  cento aliases
  cento conf
  cento conf --path
  cento kitty-theme-manager --list-custom
  cento monk
  cento cyber
USAGE
}

expand_tilde() {
    local value=$1
    if [[ "$value" == ~* ]]; then
        printf '%s\n' "${value/#\~/$HOME}"
        return
    fi
    printf '%s\n' "$value"
}

ensure_config_file() {
    cento_ensure_dir "$CONFIG_DIR"
    if [[ ! -f "$CONFIG_FILE" ]]; then
        cp "$CONFIG_TEMPLATE" "$CONFIG_FILE"
    fi
}

cento_alias() {
    local name=${1:-}
    local description=""
    shift || true

    [[ -n "$name" ]] || cento_die "Alias name is required"

    if [[ ${1:-} == "--description" ]]; then
        description=${2:-}
        shift 2 || true
    fi

    [[ ${1:-} == "--" ]] || cento_die "Alias '$name' must use '--' before the command"
    shift
    [[ $# -gt 0 ]] || cento_die "Alias '$name' must define a command"

    local serialized
    printf -v serialized '%q ' "$@"
    CENTO_ALIAS_COMMANDS["$name"]=${serialized% }
    CENTO_ALIAS_DESCRIPTIONS["$name"]=$description
}

load_config() {
    ensure_config_file
    CENTO_ALIAS_COMMANDS=()
    CENTO_ALIAS_DESCRIPTIONS=()
    # shellcheck disable=SC1090
    source "$CONFIG_FILE"
}

choose_editor() {
    local candidate
    for candidate in "${VISUAL:-}" "${EDITOR:-}" nvim vim nano vi; do
        [[ -n "$candidate" ]] || continue
        if cento_have_cmd "$candidate"; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    return 1
}

open_config() {
    ensure_config_file
    if [[ ${1:-} == "--path" ]]; then
        printf '%s\n' "$CONFIG_FILE"
        return 0
    fi

    local editor
    editor=$(choose_editor) || cento_die "No editor found via VISUAL, EDITOR, nvim, vim, nano, or vi"
    exec "$editor" "$CONFIG_FILE"
}

list_aliases() {
    load_config

    if [[ ${#CENTO_ALIAS_COMMANDS[@]} -eq 0 ]]; then
        printf 'No cento aliases configured. Edit %s\n' "$CONFIG_FILE"
        return 0
    fi

    local name
    while IFS= read -r name; do
        printf '%-18s  %-32s  %s\n' \
            "$name" \
            "${CENTO_ALIAS_DESCRIPTIONS[$name]:-}" \
            "${CENTO_ALIAS_COMMANDS[$name]}"
    done < <(printf '%s\n' "${!CENTO_ALIAS_COMMANDS[@]}" | sort)
}

list_tools() {
    python3 - "$TOOLS_JSON" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text())
for tool in sorted(data["tools"], key=lambda item: item["id"]):
    print(f"{tool['id']:<22}  {tool['name']:<24}  {tool.get('description', '')}")
PY
}

resolve_tool() {
    local tool_id=$1
    python3 - "$TOOLS_JSON" "$tool_id" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
tool_id = sys.argv[2]
data = json.loads(path.read_text())
for tool in data["tools"]:
    if tool["id"] == tool_id:
        print(tool.get("kind", ""))
        print(tool.get("wrapper", ""))
        print(tool.get("entrypoint", ""))
        raise SystemExit(0)
raise SystemExit(1)
PY
}

tool_exists() {
    python3 - "$TOOLS_JSON" "$1" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
tool_id = sys.argv[2]
data = json.loads(path.read_text())
raise SystemExit(0 if any(tool["id"] == tool_id for tool in data["tools"]) else 1)
PY
}

run_tool() {
    local tool_id=$1
    shift || true

    local kind wrapper entrypoint
    mapfile -t _tool_meta < <(resolve_tool "$tool_id") || cento_die "Unknown tool: $tool_id"
    kind=${_tool_meta[0]:-}
    wrapper=${_tool_meta[1]:-}
    entrypoint=${_tool_meta[2]:-}

    if [[ -n "$wrapper" ]]; then
        wrapper=$(expand_tilde "$wrapper")
        if [[ -x "$wrapper" ]]; then
            exec "$wrapper" "$@"
        fi
    fi

    entrypoint=${entrypoint#./}
    local target="$ROOT_DIR/$entrypoint"
    [[ -f "$target" ]] || cento_die "Tool entrypoint missing: $target"

    case "$kind" in
        python)
            exec python3 "$target" "$@"
            ;;
        shell|bash|sh|*)
            exec "$target" "$@"
            ;;
    esac
}

run_alias_with_args() {
    local alias_name=$1
    shift || true

    load_config
    [[ -n ${CENTO_ALIAS_COMMANDS[$alias_name]:-} ]] || cento_die "Unknown alias: $alias_name"

    local serialized=${CENTO_ALIAS_COMMANDS[$alias_name]}
    local -a extra=("$@")
    eval "set -- $serialized"
    exec "$@" "${extra[@]}"
}

main() {
    local command=${1:-help}
    if [[ $# -gt 0 ]]; then
        shift
    fi

    case "$command" in
        help|-h|--help)
            usage
            ;;
        tools)
            list_tools
            ;;
        aliases)
            list_aliases
            ;;
        conf)
            open_config "$@"
            ;;
        run)
            [[ $# -gt 0 ]] || cento_die "Usage: cento run TOOL [args...]"
            local tool_id=$1
            shift
            run_tool "$tool_id" "$@"
            ;;
        *)
            load_config
            if [[ -n ${CENTO_ALIAS_COMMANDS[$command]:-} ]]; then
                run_alias_with_args "$command" "$@"
            elif tool_exists "$command"; then
                run_tool "$command" "$@"
            else
                cento_die "Unknown cento command, alias, or tool: $command"
            fi
            ;;
    esac
}

main "$@"
