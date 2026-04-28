#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$SCRIPT_DIR/lib/common.sh"

ROOT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
TOOLS_JSON="$ROOT_DIR/data/tools.json"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/cento"
CONFIG_FILE="$CONFIG_DIR/aliases.sh"
LOG_DIR="$ROOT_DIR/logs/quick-help"
LOG_FILE="$LOG_DIR/$(date '+%Y%m%d-%H%M%S')-quick-help.log"

ROFI_THEME=${ROFI_THEME:-$HOME/.config/polybar/scripts/rofi/launcher.rasi}
COPY_CMD=""
SHOW_ONLY=0

builtin_usage=$(cat <<'USAGE'
Built-ins:
  cento help
  cento interactive
  cento docs
  cento docs conf
  cento tools
  cento aliases
  cento conf
  cento conf --path
  cento completion zsh
  cento install zsh
USAGE
)

declare -A CENTO_ALIAS_COMMANDS=()
declare -A CENTO_ALIAS_DESCRIPTIONS=()

declare -a ENTRY_IDS=()
declare -a ENTRY_LINES=()
declare -A ENTRY_KIND=()
declare -A ENTRY_NAME=()
declare -A ENTRY_DESC=()
declare -A ENTRY_RUN=()
declare -A ENTRY_DETAIL=()

usage() {
    cat <<'USAGE'
Usage: quick_help.sh [options]

Options:
  --show              Show the chooser and detail UI without auto-running anything
  --copy-cmd CMD      Override clipboard helper command
  -h, --help          Show this help
USAGE
}

log() {
    local msg
    msg=$(printf '[%s] %s' "$(date '+%Y-%m-%d %H:%M:%S %z')" "$*")
    printf '%s\n' "$msg" >&2
    printf '%s\n' "$msg" >&3
}

init_logging() {
    cento_ensure_dir "$LOG_DIR"
    : > "$LOG_FILE"
    exec 3>>"$LOG_FILE"
    ln -sfn "$LOG_FILE" "$LOG_DIR/latest.log"
    log "Log file: $LOG_FILE"
}

ensure_config_file() {
    cento_ensure_dir "$CONFIG_DIR"
    if [[ ! -f "$CONFIG_FILE" ]]; then
        cp "$ROOT_DIR/templates/cento/aliases.sh" "$CONFIG_FILE"
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

load_aliases() {
    ensure_config_file
    CENTO_ALIAS_COMMANDS=()
    CENTO_ALIAS_DESCRIPTIONS=()
    # shellcheck disable=SC1090
    source "$CONFIG_FILE"
}

choose_copy_cmd() {
    if [[ -n "$COPY_CMD" ]]; then
        printf '%s\n' "$COPY_CMD"
        return
    fi
    if cento_have_cmd wl-copy; then
        printf 'wl-copy\n'
        return
    fi
    if cento_have_cmd xclip; then
        printf 'xclip -selection clipboard\n'
        return
    fi
    if cento_have_cmd xsel; then
        printf 'xsel --clipboard --input\n'
        return
    fi
    printf '\n'
}

run_rofi() {
    local -a args=(rofi)
    if [[ -f "$ROFI_THEME" ]]; then
        args+=(-theme "$ROFI_THEME")
    fi
    args+=("$@")
    "${args[@]}"
}

add_entry() {
    local id=$1
    local kind=$2
    local name=$3
    local desc=$4
    local run_cmd=$5
    local detail=$6

    ENTRY_IDS+=("$id")
    ENTRY_KIND["$id"]=$kind
    ENTRY_NAME["$id"]=$name
    ENTRY_DESC["$id"]=$desc
    ENTRY_RUN["$id"]=$run_cmd
    ENTRY_DETAIL["$id"]=$detail
    ENTRY_LINES+=("$name [$kind]  $desc")
}

build_entries() {
    add_entry \
        "builtin:help" \
        "builtin" \
        "help" \
        "Show cento CLI usage" \
        "$HOME/bin/cento help" \
        "cento built-in: help\n\nRun:\n  cento help\n\n$builtin_usage"

    add_entry \
        "builtin:tools" \
        "builtin" \
        "tools" \
        "List registered cento tools" \
        "$HOME/bin/cento tools" \
        "cento built-in: tools\n\nRun:\n  cento tools"

    add_entry \
        "builtin:aliases" \
        "builtin" \
        "aliases" \
        "List configured cento aliases" \
        "$HOME/bin/cento aliases" \
        "cento built-in: aliases\n\nRun:\n  cento aliases\n\nConfig:\n  $CONFIG_FILE"

    add_entry \
        "builtin:conf" \
        "builtin" \
        "conf" \
        "Open cento config in your editor" \
        "$HOME/bin/cento conf" \
        "cento built-in: conf\n\nRun:\n  cento conf\n\nConfig file:\n  $CONFIG_FILE"

    add_entry \
        "builtin:completion" \
        "builtin" \
        "completion" \
        "Print cento Zsh completion" \
        "$HOME/bin/cento completion zsh" \
        "cento built-in: completion\n\nRun:\n  cento completion zsh\n\nShells:\n  zsh"

    add_entry \
        "builtin:install" \
        "builtin" \
        "install" \
        "Install cento shell integration" \
        "$HOME/bin/cento install zsh" \
        "cento built-in: install\n\nRun:\n  cento install zsh\n\nWhat it does:\n  Writes managed init and completion files under ~/.config/cento and injects one guarded source block into ~/.zshrc"

    while IFS=$'\t' read -r tool_id tool_name tool_desc tool_cmds; do
        [[ -n "$tool_id" ]] || continue
        local first_cmd
        first_cmd=${tool_cmds%%|||*}
        add_entry \
            "tool:$tool_id" \
            "tool" \
            "$tool_id" \
            "$tool_desc" \
            "$HOME/bin/cento $tool_id" \
            "Tool: $tool_name\nID: $tool_id\n\nDescription:\n  $tool_desc\n\nExamples:\n  ${tool_cmds//|||/$'\n  '}\n\nRun:\n  $HOME/bin/cento $tool_id"
    done < <(python3 - "$TOOLS_JSON" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text())
for tool in sorted(data["tools"], key=lambda item: item["id"]):
    cmds = "|||".join(tool.get("commands", []))
    print("\t".join([
        tool["id"],
        tool.get("name", tool["id"]),
        tool.get("description", ""),
        cmds,
    ]))
PY
)

    load_aliases
    local name
    while IFS= read -r name; do
        [[ -n "$name" ]] || continue
        add_entry \
            "alias:$name" \
            "alias" \
            "$name" \
            "${CENTO_ALIAS_DESCRIPTIONS[$name]:-User alias}" \
            "$HOME/bin/cento $name" \
            "Alias: $name\n\nDescription:\n  ${CENTO_ALIAS_DESCRIPTIONS[$name]:-User alias}\n\nRuns:\n  ${CENTO_ALIAS_COMMANDS[$name]}\n\nInvoke:\n  $HOME/bin/cento $name"
    done < <(printf '%s\n' "${!CENTO_ALIAS_COMMANDS[@]}" | sort)
}

show_detail() {
    local id=$1
    local detail=${ENTRY_DETAIL[$id]}
    printf '%b\n' "$detail" | rofi -dmenu -i -p "cento help" -mesg "Enter: run  |  Ctrl-y: copy command  |  Esc: back" -kb-custom-1 'Control+y' -no-custom -theme "$ROFI_THEME" >/dev/null
}

choose_entry() {
    local selection
    selection=$(printf '%s\n' "${ENTRY_LINES[@]}" | run_rofi -dmenu -i -p "cento help" -mesg "Search cento commands, tools, and aliases") || return 1
    local i
    for i in "${!ENTRY_LINES[@]}"; do
        if [[ "${ENTRY_LINES[$i]}" == "$selection" ]]; then
            printf '%s\n' "${ENTRY_IDS[$i]}"
            return 0
        fi
    done
    return 1
}

choose_action() {
    local id=$1
    local run_cmd=${ENTRY_RUN[$id]}
    local detail=${ENTRY_DETAIL[$id]}
    local actions
    actions=$(cat <<EOF_ACTIONS
show  Show help text
run   Run: $run_cmd
copy  Copy run command
conf  Open cento config
EOF_ACTIONS
)
    local choice
    choice=$(printf '%s\n' "$actions" | run_rofi -dmenu -i -p "${ENTRY_NAME[$id]}" -mesg "$detail") || return 1
    printf '%s\n' "${choice%% *}"
}

copy_command() {
    local cmd=$1
    local copier
    copier=$(choose_copy_cmd)
    if [[ -z "$copier" ]]; then
        run_rofi -e "No clipboard tool found (wl-copy/xclip/xsel)." >/dev/null
        return 1
    fi
    printf '%s' "$cmd" | eval "$copier"
}

run_selected() {
    local id=$1
    local cmd=${ENTRY_RUN[$id]}
    log "Running: $cmd"
    exec bash -lc "$cmd"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --show)
            SHOW_ONLY=1
            shift
            ;;
        --copy-cmd)
            COPY_CMD=$2
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            cento_die "Unknown argument: $1"
            ;;
    esac
done

cento_require_cmd rofi
cento_require_cmd python3
init_logging
build_entries

while true; do
    selected_id=$(choose_entry) || exit 0
    action=$(choose_action "$selected_id") || continue
    case "$action" in
        show)
            continue
            ;;
        run)
            if [[ "$SHOW_ONLY" -eq 1 ]]; then
                show_detail "$selected_id"
            else
                run_selected "$selected_id"
            fi
            ;;
        copy)
            copy_command "${ENTRY_RUN[$selected_id]}" || true
            ;;
        conf)
            exec "$HOME/bin/cento" conf
            ;;
    esac
done
