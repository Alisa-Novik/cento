#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$SCRIPT_DIR/lib/common.sh"

KITTY_CONFIG_DIR=${KITTY_CONFIG_DIRECTORY:-$HOME/.config/kitty}
KITTY_CONF_FILE="$KITTY_CONFIG_DIR/kitty.conf"
CURRENT_THEME_FILE="$KITTY_CONFIG_DIR/current-theme.conf"
THEME_SOURCE_DIR="$SCRIPT_DIR/../themes/kitty"
THEME_TARGET_DIR="$KITTY_CONFIG_DIR/themes"
LOG_ROOT="$SCRIPT_DIR/../logs/kitty-theme-manager"
LOG_FILE=""
THEME_NAME=""
LIST_CUSTOM=0
SYNC_ONLY=0
NO_TMUX_RELOAD=0
PLAIN_MENU=0
TMUX_CONF=${TMUX_CONF:-$HOME/.tmux.conf}
ORIGINAL_ARGS=("$@")

usage() {
    cat <<'USAGE'
Usage: kitty_theme_manager.sh [options]

Options:
  --theme NAME         Apply a theme non-interactively
  --log-file PATH      Write logs to a specific file
  --list-custom        List custom themes shipped by cento
  --sync-only          Copy cento themes into Kitty's themes directory and exit
  --plain-menu         Use a numbered prompt instead of fzf
  --no-tmux-reload     Skip tmux refresh/reload steps
  --tmux-conf PATH     Tmux config file to source when reloading tmux
  -h, --help           Show this help
USAGE
}

sync_custom_themes() {
    cento_ensure_dir "$THEME_TARGET_DIR"
    find "$THEME_SOURCE_DIR" -maxdepth 1 -type f -name '*.conf' | while IFS= read -r theme_file; do
        cp "$theme_file" "$THEME_TARGET_DIR/$(basename "$theme_file")"
    done
}

timestamp() {
    date '+%Y-%m-%d %H:%M:%S %z'
}

log() {
    printf '[%s] %s\n' "$(timestamp)" "$*"
}

run_logged() {
    local label=$1
    shift

    log "RUN $label: $*"
    "$@"
    local status=$?
    if [[ "$status" -eq 0 ]]; then
        log "OK  $label"
        return 0
    fi

    log "ERR $label (exit $status)"
    return "$status"
}

init_logging() {
    cento_ensure_dir "$LOG_ROOT"

    if [[ -z "$LOG_FILE" ]]; then
        LOG_FILE="$LOG_ROOT/$(date '+%Y%m%d-%H%M%S')-kitty-theme-manager.log"
    fi

    cento_ensure_dir "$(dirname "$LOG_FILE")"
    : > "$LOG_FILE"
    ln -sfn "$LOG_FILE" "$LOG_ROOT/latest.log"
    exec > >(tee -a "$LOG_FILE") 2>&1

    log "Log file: $LOG_FILE"
    log "PWD: $PWD"
    log "Script: $0"
    log "Args: ${ORIGINAL_ARGS[*]:-}"
    log "TMUX=${TMUX:-}"
    log "TMUX_PANE=${TMUX_PANE:-}"
    log "KITTY_WINDOW_ID=${KITTY_WINDOW_ID:-}"
    log "KITTY_PID=${KITTY_PID:-}"
    log "KITTY_INSTALLATION_DIR=${KITTY_INSTALLATION_DIR:-}"
}

list_custom_themes() {
    find "$THEME_SOURCE_DIR" -maxdepth 1 -type f -name '*.conf' -printf '%f\n' \
        | sed 's/\.conf$//' \
        | sort
}

select_theme_interactively() {
    local -a themes
    mapfile -t themes < <(printf 'Default\n'; list_custom_themes)

    if [[ "$PLAIN_MENU" -eq 0 ]] && cento_have_cmd fzf && [[ -t 0 && -t 1 ]]; then
        printf '%s\n' "${themes[@]}" | fzf --height=40% --layout=reverse --border --prompt='Kitty theme> '
        return
    fi

    local i=1
    printf 'Select Kitty theme:\n' >&2
    for theme in "${themes[@]}"; do
        printf '  %d) %s\n' "$i" "$theme" >&2
        i=$((i + 1))
    done
    printf 'Choice: ' >&2
    read -r choice
    [[ "$choice" =~ ^[0-9]+$ ]] || cento_die "Invalid selection"
    (( choice >= 1 && choice <= ${#themes[@]} )) || cento_die "Selection out of range"
    printf '%s\n' "${themes[$((choice - 1))]}"
}

update_kitty_conf_block() {
    local theme=$1
    KITTY_CONF_FILE="$KITTY_CONF_FILE" THEME_NAME="$theme" python3 - <<'PY'
from pathlib import Path
import os

path = Path(os.environ["KITTY_CONF_FILE"])
theme = os.environ["THEME_NAME"]
block = f"# BEGIN_KITTY_THEME\n# {theme}\ninclude current-theme.conf\n# END_KITTY_THEME\n"
text = path.read_text() if path.exists() else ""
start = "# BEGIN_KITTY_THEME"
end = "# END_KITTY_THEME"
if start in text and end in text:
    before, rest = text.split(start, 1)
    _, after = rest.split(end, 1)
    new_text = before.rstrip() + "\n\n" + block + after
else:
    new_text = text.rstrip() + "\n\n" + block if text.strip() else block
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(new_text)
PY
}

reload_kitty_if_possible() {
    local attempted=0

    if [[ -n "${KITTY_PID:-}" ]]; then
        attempted=1
        run_logged "kitty-sigusr1" kill -SIGUSR1 "$KITTY_PID" || true
    fi

    if cento_have_cmd pkill; then
        attempted=1
        run_logged "kitty-pkill-sigusr1" pkill -SIGUSR1 -x kitty || true
    fi

    if [[ -n "${KITTY_LISTEN_ON:-}" ]] && cento_have_cmd kitty; then
        attempted=1
        run_logged "kitty-remote-load-config" kitty @ --to "$KITTY_LISTEN_ON" load-config "$KITTY_CONF_FILE" || true
    elif [[ -n "${KITTY_LISTEN_ON:-}" ]] && cento_have_cmd kitten; then
        attempted=1
        run_logged "kitten-remote-load-config" kitten @ --to "$KITTY_LISTEN_ON" load-config "$KITTY_CONF_FILE" || true
    else
        log "Skipping kitty remote control reload because KITTY_LISTEN_ON is not set"
    fi

    if [[ "$attempted" -eq 0 ]]; then
        log "No Kitty runtime detected; skipped Kitty reload"
    fi
}

reload_tmux_if_needed() {
    if [[ "$NO_TMUX_RELOAD" -eq 1 || -z "${TMUX:-}" ]]; then
        log "Skipping tmux reload"
        return 0
    fi

    if [[ -f "$TMUX_CONF" ]]; then
        run_logged "tmux-source-file" tmux source-file "$TMUX_CONF" || true
    else
        log "Tmux config not found: $TMUX_CONF"
    fi
    run_logged "tmux-refresh-client-S" tmux refresh-client -S || true
    run_logged "tmux-refresh-client" tmux refresh-client || true
    run_logged "tmux-display-message" tmux display-message "Kitty theme updated" || true
}

apply_theme() {
    local theme=$1
    cento_ensure_dir "$KITTY_CONFIG_DIR"

    if [[ "$theme" == "Default" ]]; then
        : > "$CURRENT_THEME_FILE"
        log "Applied Default theme by clearing $CURRENT_THEME_FILE"
    else
        local source_file="$THEME_SOURCE_DIR/$theme.conf"
        [[ -f "$source_file" ]] || cento_die "Theme not found: $theme"
        cp "$source_file" "$CURRENT_THEME_FILE"
        log "Copied theme file: $source_file -> $CURRENT_THEME_FILE"
    fi

    update_kitty_conf_block "$theme"
    log "Updated Kitty config block in $KITTY_CONF_FILE"
    reload_kitty_if_possible
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --theme)
            THEME_NAME=$2
            shift 2
            ;;
        --log-file)
            LOG_FILE=$2
            shift 2
            ;;
        --list-custom)
            LIST_CUSTOM=1
            shift
            ;;
        --sync-only)
            SYNC_ONLY=1
            shift
            ;;
        --plain-menu)
            PLAIN_MENU=1
            shift
            ;;
        --no-tmux-reload)
            NO_TMUX_RELOAD=1
            shift
            ;;
        --tmux-conf)
            TMUX_CONF=$2
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

init_logging
cento_require_cmd kitty
cento_require_cmd python3
[[ -d "$THEME_SOURCE_DIR" ]] || cento_die "Theme source directory not found: $THEME_SOURCE_DIR"

if [[ "$LIST_CUSTOM" -eq 1 ]]; then
    list_custom_themes
    exit 0
fi

sync_custom_themes
log "Synced custom themes into $THEME_TARGET_DIR"

if [[ "$SYNC_ONLY" -eq 1 ]]; then
    printf '%s\n' "$THEME_TARGET_DIR"
    exit 0
fi

if [[ -z "$THEME_NAME" ]]; then
    THEME_NAME=$(select_theme_interactively)
    [[ -n "$THEME_NAME" ]] || exit 1
fi

log "Selected theme: $THEME_NAME"
apply_theme "$THEME_NAME"
reload_tmux_if_needed
log "Completed successfully"
printf 'Applied Kitty theme: %s\n' "$THEME_NAME"
printf 'Log saved to: %s\n' "$LOG_FILE"
