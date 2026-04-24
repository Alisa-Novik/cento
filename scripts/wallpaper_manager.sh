#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$SCRIPT_DIR/lib/common.sh"

ROOT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/cento"
STATE_FILE="$CONFIG_DIR/wallpaper.env"
LOG_DIR="$ROOT_DIR/logs/wallpaper-manager"
LOG_FILE="$LOG_DIR/$(date '+%Y%m%d-%H%M%S')-wallpaper-manager.log"
DEFAULT_LIBRARY_DIR="$HOME/.config/kitty"
DEFAULT_MODE="--bg-scale"
PICOM_CONFIG=${PICOM_CONFIG:-$HOME/.config/picom/picom.conf}
CHOOSE=0
LIST=0
APPLY_CURRENT=0
IMPORT_DOWNLOADS=0
SHOW_PATH=0
NO_PREVIEW=0
WALLPAPER_PATH=""
WALLPAPER_NAME=""
LIBRARY_DIR=""

usage() {
    cat <<'USAGE'
Usage: wallpaper_manager.sh [options]

Options:
  --choose               Pick a wallpaper interactively
  --list                 List available wallpapers
  --set PATH_OR_NAME     Apply a wallpaper by full path or basename
  --apply-current        Re-apply the saved current wallpaper from state
  --show-path            Print the current wallpaper path
  --library-dir PATH     Override the wallpaper library directory
  --import-downloads     Copy top-level images from ~/Downloads into the library
  --no-preview           Disable visual preview in the interactive picker
  -h, --help             Show this help
USAGE
}

log() {
    printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S %z')" "$*"
}

init_logging() {
    cento_ensure_dir "$LOG_DIR"
    exec > >(tee -a "$LOG_FILE") 2>&1
    ln -sfn "$LOG_FILE" "$LOG_DIR/latest.log"
    log "Log file: $LOG_FILE"
}

ensure_state_dir() {
    cento_ensure_dir "$CONFIG_DIR"
}

discover_current_from_i3() {
    local i3_config="$HOME/.config/i3/config"
    [[ -f "$i3_config" ]] || return 0

    python3 - "$i3_config" <<'PYI3'
from pathlib import Path
import re
import sys

text = Path(sys.argv[1]).read_text()
for line in text.splitlines():
    if 'feh ' not in line:
        continue
    match = re.search(r'feh\s+--bg-[^ ]+\s+(.+)$', line.strip())
    if not match:
        continue
    value = match.group(1).strip().strip('"').strip("'")
    value = value.replace('~/', str(Path.home()) + '/')
    print(value)
    break
PYI3
}

load_state() {
    ensure_state_dir
    if [[ -f "$STATE_FILE" ]]; then
        # shellcheck disable=SC1090
        source "$STATE_FILE"
    fi

    LIBRARY_DIR=${LIBRARY_DIR:-${WALLPAPER_LIBRARY_DIR:-$DEFAULT_LIBRARY_DIR}}
    [[ -d "$LIBRARY_DIR" ]] && LIBRARY_DIR=$(cd -- "$LIBRARY_DIR" && pwd -P)
    WALLPAPER_PATH=${WALLPAPER_PATH:-${CURRENT_WALLPAPER:-}}
    if [[ -z "$WALLPAPER_PATH" ]]; then
        WALLPAPER_PATH=$(discover_current_from_i3 || true)
    fi
}

save_state() {
    ensure_state_dir
    cat > "$STATE_FILE" <<EOFSTATE
WALLPAPER_LIBRARY_DIR=$(printf '%q' "$LIBRARY_DIR")
CURRENT_WALLPAPER=$(printf '%q' "$WALLPAPER_PATH")
WALLPAPER_MODE=$(printf '%q' "$DEFAULT_MODE")
EOFSTATE
}

list_wallpapers() {
    find "$LIBRARY_DIR" -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' \) | sort
}

fzf_preview_command() {
    cat <<'EOF_PREVIEW'
path=$(printf '%s' {2})
if command -v kitten >/dev/null 2>&1 && [ -n "${KITTY_WINDOW_ID:-}" ] && [ -z "${TMUX:-}" ]; then
  kitten icat --clear --stdin=no --transfer-mode=file --place="${FZF_PREVIEW_COLUMNS}x${FZF_PREVIEW_LINES}@0x0" "$path" 2>/dev/null || file "$path"
elif command -v kitten >/dev/null 2>&1 && [ -n "${KITTY_WINDOW_ID:-}" ]; then
  kitten icat --clear --stdin=no --transfer-mode=file --place="${FZF_PREVIEW_COLUMNS}x${FZF_PREVIEW_LINES}@0x0" "$path" 2>/dev/null || file "$path"
else
  file "$path"
fi
EOF_PREVIEW
}

select_interactively() {
    local -a files
    mapfile -t files < <(list_wallpapers)
    [[ ${#files[@]} -gt 0 ]] || cento_die "No wallpapers found in $LIBRARY_DIR"

    if cento_have_cmd fzf && [[ -t 0 && -t 1 ]]; then
        local preview_args=()
        if [[ "$NO_PREVIEW" -eq 0 ]]; then
            preview_args=(
                --preview "$(fzf_preview_command)"
                --preview-window 'right,65%,border-left'
            )
        fi

        printf '%s\n' "${files[@]}" | while IFS= read -r path; do
            printf '%s\t%s\n' "$(basename "$path")" "$path"
        done | fzf \
            --height=70% \
            --layout=reverse \
            --border \
            --prompt='Wallpaper> ' \
            --delimiter=$'\t' \
            --with-nth=1,2 \
            "${preview_args[@]}" \
            | awk -F '\t' '{print $2}'
        return
    fi

    local i=1
    printf 'Select wallpaper:\n' >&2
    for path in "${files[@]}"; do
        printf '  %d) %s\n' "$i" "$(basename "$path")" >&2
        i=$((i + 1))
    done
    printf 'Choice: ' >&2
    local choice
    read -r choice
    [[ "$choice" =~ ^[0-9]+$ ]] || cento_die "Invalid selection"
    (( choice >= 1 && choice <= ${#files[@]} )) || cento_die "Selection out of range"
    printf '%s\n' "${files[$((choice - 1))]}"
}

resolve_wallpaper() {
    local input=$1
    if [[ -f "$input" ]]; then
        printf '%s\n' "$input"
        return
    fi
    if [[ -f "$LIBRARY_DIR/$input" ]]; then
        printf '%s\n' "$LIBRARY_DIR/$input"
        return
    fi
    local match
    match=$(find "$LIBRARY_DIR" -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' \) -printf '%f\n' | rg -x -F "$input" -m 1 || true)
    if [[ -n "$match" && -f "$LIBRARY_DIR/$match" ]]; then
        printf '%s\n' "$LIBRARY_DIR/$match"
        return
    fi
    cento_die "Wallpaper not found: $input"
}

refresh_picom() {
    log "Refreshing picom"
    if pgrep -x picom >/dev/null 2>&1; then
        pkill -x picom || true
        sleep 0.2
    fi

    if [[ -f "$PICOM_CONFIG" ]]; then
        picom --config "$PICOM_CONFIG" --daemon >/dev/null 2>&1 || cento_warn "Failed to restart picom with config $PICOM_CONFIG"
    else
        picom --daemon >/dev/null 2>&1 || cento_warn "Failed to restart picom"
    fi
}

apply_wallpaper() {
    local path=$1
    [[ -f "$path" ]] || cento_die "Wallpaper file missing: $path"
    log "Applying wallpaper: $path"
    feh "$DEFAULT_MODE" "$path"
    refresh_picom
    WALLPAPER_PATH=$path
    save_state
    log "Saved current wallpaper to $STATE_FILE"
}

import_downloads() {
    local source_dir="$HOME/Downloads"
    [[ -d "$source_dir" ]] || cento_die "Downloads directory not found: $source_dir"
    cento_ensure_dir "$LIBRARY_DIR"
    find "$source_dir" -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' \) | while IFS= read -r file; do
        cp -n "$file" "$LIBRARY_DIR/$(basename "$file")"
    done
    log "Imported top-level Downloads images into $LIBRARY_DIR"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --choose)
            CHOOSE=1
            shift
            ;;
        --list)
            LIST=1
            shift
            ;;
        --set)
            WALLPAPER_NAME=$2
            shift 2
            ;;
        --apply-current)
            APPLY_CURRENT=1
            shift
            ;;
        --show-path)
            SHOW_PATH=1
            shift
            ;;
        --library-dir)
            LIBRARY_DIR=$2
            shift 2
            ;;
        --import-downloads)
            IMPORT_DOWNLOADS=1
            shift
            ;;
        --no-preview)
            NO_PREVIEW=1
            shift
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
cento_require_cmd feh
cento_require_cmd python3
load_state
cento_ensure_dir "$LIBRARY_DIR"
log "Library dir: $LIBRARY_DIR"

if [[ "$IMPORT_DOWNLOADS" -eq 1 ]]; then
    import_downloads
fi

if [[ "$LIST" -eq 1 ]]; then
    list_wallpapers
    exit 0
fi

if [[ "$SHOW_PATH" -eq 1 ]]; then
    printf '%s\n' "$WALLPAPER_PATH"
    exit 0
fi

if [[ "$APPLY_CURRENT" -eq 1 ]]; then
    [[ -n "$WALLPAPER_PATH" ]] || cento_die "No current wallpaper saved in $STATE_FILE"
    apply_wallpaper "$WALLPAPER_PATH"
    exit 0
fi

if [[ -n "$WALLPAPER_NAME" ]]; then
    WALLPAPER_PATH=$(resolve_wallpaper "$WALLPAPER_NAME")
    apply_wallpaper "$WALLPAPER_PATH"
    exit 0
fi

if [[ "$CHOOSE" -eq 1 || $# -eq 0 ]]; then
    WALLPAPER_PATH=$(select_interactively)
    [[ -n "$WALLPAPER_PATH" ]] || exit 1
    apply_wallpaper "$WALLPAPER_PATH"
    exit 0
fi
