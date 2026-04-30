#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$SCRIPT_DIR/lib/common.sh"

[[ "$(uname -s)" == "Darwin" ]] || cento_die "industrial-macos is a macOS-only preset"

ROOT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
CONFIG_ROOT="${XDG_CONFIG_HOME:-$HOME/.config}/cento"
DATA_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}/cento/industrial-macos"
STATE_ROOT="${XDG_STATE_HOME:-$HOME/.local/state}/cento/industrial-macos"
LOG_DIR="$ROOT_DIR/logs/industrial-macos"
LOG_FILE="$LOG_DIR/$(date '+%Y%m%d-%H%M%S')-industrial-macos.log"
PRESET_ENV="$CONFIG_ROOT/preset.env"
KITTY_THEME="Cento Industrial Mac"
WALLPAPER_SOURCE="$ROOT_DIR/assets/industrial-os/volcano-pane.png"
WALLPAPER_FILE="$DATA_ROOT/wallpaper.png"
DASHBOARD_HOST=${CENTO_INDUSTRIAL_MAC_DASHBOARD_HOST:-127.0.0.1}
DASHBOARD_PORT=${CENTO_INDUSTRIAL_MAC_DASHBOARD_PORT:-46269}
DASHBOARD_LABEL="com.cento.industrial-mac-dashboard"
DASHBOARD_PID_FILE="$STATE_ROOT/dashboard.pid"
DASHBOARD_URL_FILE="$STATE_ROOT/dashboard.url"
DASHBOARD_PROCESS_LOG="$STATE_ROOT/dashboard.log"
DASHBOARD_PLIST="$STATE_ROOT/dashboard.plist"

DASHBOARD_ONLY=0
OPEN_DASHBOARD=1
START_DASHBOARD=1
APPLY_RUNTIME=1
CURRENT_SPACE_ONLY=0

usage() {
    cat <<'USAGE'
Usage: cento preset industrial-macos [options]

Options:
  --dashboard-only   Start or reuse the themed dashboard server only.
  --open             Open the themed dashboard after starting it.
  --no-open          Do not open the themed dashboard.
  --no-dashboard     Do not start the dashboard server.
  --current-space    Only set wallpaper on the current Space.
  --status           Print managed preset paths and dashboard status.
  -h, --help         Show this help.
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

write_preset_state() {
    cento_ensure_dir "$CONFIG_ROOT"
    cat > "$PRESET_ENV" <<EOF_STATE
CENTO_PRESET=industrial-macos
CENTO_PRESET_NAME=$(printf '%q' "Industrial Mac")
CENTO_PRESET_APPLIED_AT=$(printf '%q' "$(date '+%Y-%m-%dT%H:%M:%S%z')")
CENTO_WALLPAPER=$(printf '%q' "$WALLPAPER_FILE")
CENTO_KITTY_THEME=$(printf '%q' "$KITTY_THEME")
CENTO_DASHBOARD_THEME=industrial
CENTO_DASHBOARD_URL=$(printf '%q' "http://$DASHBOARD_HOST:$DASHBOARD_PORT")
EOF_STATE
}

install_wallpaper_asset() {
    [[ -f "$WALLPAPER_SOURCE" ]] || cento_die "Missing Industrial OS artwork: $WALLPAPER_SOURCE"
    cento_ensure_dir "$DATA_ROOT"
    cp "$WALLPAPER_SOURCE" "$WALLPAPER_FILE"
    cat > "$CONFIG_ROOT/wallpaper.env" <<EOF_WALLPAPER
WALLPAPER_LIBRARY_DIR=$(printf '%q' "$DATA_ROOT")
CURRENT_WALLPAPER=$(printf '%q' "$WALLPAPER_FILE")
WALLPAPER_MODE=macos-desktop-picture
EOF_WALLPAPER
}

apply_kitty_theme() {
    if [[ -x "$HOME/bin/cento" ]]; then
        "$HOME/bin/cento" kitty-theme-manager --theme "$KITTY_THEME" || cento_warn "Kitty theme apply failed"
    else
        "$ROOT_DIR/scripts/kitty_theme_manager.sh" --theme "$KITTY_THEME" || cento_warn "Kitty theme apply failed"
    fi

    if cento_have_cmd kitten; then
        kitten @ set-colors -a "$HOME/.config/kitty/current-theme.conf" >/dev/null 2>&1 \
            && log "Applied Kitty colors to the active Kitty session" \
            || apply_kitty_tty_colors
    fi
}

apply_kitty_tty_colors() {
    local updated
    updated=$(python3 - "$HOME/.config/kitty/current-theme.conf" <<'PY'
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

theme_path = Path(sys.argv[1])
colors: dict[str, str] = {}
for raw in theme_path.read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if not line or line.startswith("#"):
        continue
    parts = line.split(None, 1)
    if len(parts) == 2:
        colors[parts[0]] = parts[1].strip()

kitty_pids = {
    item.strip()
    for item in subprocess.run(["pgrep", "-x", "kitty"], capture_output=True, text=True, check=False).stdout.splitlines()
    if item.strip()
}
if not kitty_pids:
    print("0")
    raise SystemExit(0)

ps_output = subprocess.run(["ps", "-axo", "ppid=,tty=,command="], capture_output=True, text=True, check=False).stdout
ttys: set[str] = set()
for line in ps_output.splitlines():
    match = re.match(r"\s*(\d+)\s+(\S+)\s+(.+)$", line)
    if not match:
        continue
    ppid, tty, command = match.groups()
    if ppid in kitty_pids and tty.startswith("ttys") and "kitten run-shell" in command:
        ttys.add(f"/dev/{tty}")

seq = []
if "foreground" in colors:
    seq.append(f"\033]10;{colors['foreground']}\007")
if "background" in colors:
    seq.append(f"\033]11;{colors['background']}\007")
if "cursor" in colors:
    seq.append(f"\033]12;{colors['cursor']}\007")
if "selection_background" in colors:
    seq.append(f"\033]17;{colors['selection_background']}\007")
if "selection_foreground" in colors:
    seq.append(f"\033]19;{colors['selection_foreground']}\007")
for index in range(16):
    value = colors.get(f"color{index}")
    if value:
        seq.append(f"\033]4;{index};{value}\007")
payload = "".join(seq).encode()

updated = 0
for tty in sorted(ttys):
    try:
        fd = os.open(tty, os.O_WRONLY | os.O_NONBLOCK)
        try:
            os.write(fd, payload)
            updated += 1
        finally:
            os.close(fd)
    except OSError:
        pass
print(updated)
PY
)
    if [[ "$updated" -eq 0 ]]; then
        cento_warn "Existing Kitty windows may need a restart to pick up $KITTY_THEME"
    else
        log "Applied Kitty colors through OSC to $updated Kitty TTY(s)"
    fi
}

set_current_space_wallpaper() {
    if ! cento_have_cmd osascript; then
        cento_warn "osascript is not installed; skipping wallpaper apply"
        return 0
    fi
    osascript -e "tell application \"System Events\" to tell every desktop to set picture to POSIX file \"$WALLPAPER_FILE\"" >/dev/null 2>&1 \
        || cento_warn "macOS wallpaper apply failed"
}

space_count() {
    python3 - <<'PY'
import plistlib
from pathlib import Path

path = Path.home() / "Library/Preferences/com.apple.spaces.plist"
try:
    data = plistlib.loads(path.read_bytes())
    monitors = data["SpacesDisplayConfiguration"]["Management Data"].get("Monitors", [])
    print(max((len(m.get("Spaces", [])) for m in monitors), default=1))
except Exception:
    print(1)
PY
}

switch_space() {
    local direction=$1
    local key_code=124
    [[ "$direction" == "left" ]] && key_code=123
    osascript -e "tell application \"System Events\" to key code $key_code using control down" >/dev/null 2>&1 || return 1
}

apply_wallpaper() {
    set_current_space_wallpaper
    if [[ "$CURRENT_SPACE_ONLY" -eq 1 ]]; then
        log "Applied macOS wallpaper on current Space: $WALLPAPER_FILE"
        return 0
    fi

    local spaces
    spaces=$(space_count)
    [[ "$spaces" =~ ^[0-9]+$ ]] || spaces=1
    if (( spaces > 1 )); then
        log "Applying macOS wallpaper across $spaces Spaces"
        local index
        for ((index = 1; index < spaces; index++)); do
            switch_space right || {
                cento_warn "Could not switch Spaces; Accessibility permission may be required"
                break
            }
            sleep 0.45
            set_current_space_wallpaper
        done
        for ((index = 1; index < spaces; index++)); do
            switch_space left || break
            sleep 0.18
        done
    fi
    log "Applied macOS wallpaper: $WALLPAPER_FILE"
}

dashboard_alive() {
    local pid
    [[ -f "$DASHBOARD_PID_FILE" ]] || return 1
    pid=$(<"$DASHBOARD_PID_FILE")
    [[ "$pid" =~ ^[0-9]+$ ]] || return 1
    kill -0 "$pid" >/dev/null 2>&1 || return 1
    ps -p "$pid" -o command= 2>/dev/null | grep -Fq "dashboard_server.py" || return 1
}

open_dashboard_url() {
    local url=${1:-}
    [[ -n "$url" && "$OPEN_DASHBOARD" -eq 1 ]] || return 0
    open "$url" >/dev/null 2>&1 || true
}

start_dashboard() {
    [[ "$START_DASHBOARD" -eq 1 ]] || return 0
    cento_ensure_dir "$STATE_ROOT"
    if dashboard_alive; then
        local existing_url
        existing_url=$(cat "$DASHBOARD_URL_FILE" 2>/dev/null || true)
        [[ -n "$existing_url" ]] || existing_url="http://$DASHBOARD_HOST:$DASHBOARD_PORT"
        log "Industrial Mac dashboard already running: $existing_url"
        open_dashboard_url "$existing_url"
        return 0
    fi

    : > "$DASHBOARD_PROCESS_LOG"
    local python_bin
    python_bin=$(command -v python3)
    cat > "$DASHBOARD_PLIST" <<EOF_PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$DASHBOARD_LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$python_bin</string>
    <string>$ROOT_DIR/scripts/dashboard_server.py</string>
    <string>--host</string>
    <string>$DASHBOARD_HOST</string>
    <string>--port</string>
    <string>$DASHBOARD_PORT</string>
    <string>--theme</string>
    <string>industrial</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <false/>
  <key>WorkingDirectory</key>
  <string>$ROOT_DIR</string>
  <key>StandardOutPath</key>
  <string>$DASHBOARD_PROCESS_LOG</string>
  <key>StandardErrorPath</key>
  <string>$DASHBOARD_PROCESS_LOG</string>
</dict>
</plist>
EOF_PLIST

    launchctl bootout "gui/$(id -u)" "$DASHBOARD_PLIST" >/dev/null 2>&1 || true
    launchctl bootstrap "gui/$(id -u)" "$DASHBOARD_PLIST"
    launchctl kickstart -k "gui/$(id -u)/$DASHBOARD_LABEL" >/dev/null 2>&1 || true
    sleep 0.8
    if cento_have_cmd lsof; then
        lsof -tiTCP:"$DASHBOARD_PORT" -sTCP:LISTEN | head -1 > "$DASHBOARD_PID_FILE" || true
    else
        pgrep -f "$ROOT_DIR/scripts/dashboard_server.py.*--port $DASHBOARD_PORT.*--theme industrial" | head -1 > "$DASHBOARD_PID_FILE" || true
    fi

    local url="http://$DASHBOARD_HOST:$DASHBOARD_PORT"
    printf '%s\n' "$url" > "$DASHBOARD_URL_FILE"
    if ! dashboard_alive; then
        cat "$DASHBOARD_PROCESS_LOG" >&2 || true
        cento_die "Industrial Mac dashboard failed to stay running"
    fi
    log "Industrial Mac dashboard running: $url"
    open_dashboard_url "$url"
}

write_assets() {
    install_wallpaper_asset
    write_preset_state
}

apply_runtime() {
    write_assets
    apply_kitty_theme
    apply_wallpaper
    start_dashboard
}

print_status() {
    printf 'preset: industrial-macos\n'
    printf 'kitty theme: %s\n' "$KITTY_THEME"
    printf 'wallpaper: %s\n' "$WALLPAPER_FILE"
    printf 'preset env: %s\n' "$PRESET_ENV"
    printf 'dashboard plist: %s\n' "$DASHBOARD_PLIST"
    if dashboard_alive; then
        printf 'dashboard: running %s\n' "$(cat "$DASHBOARD_URL_FILE" 2>/dev/null || true)"
    else
        printf 'dashboard: stopped\n'
    fi
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dashboard-only)
            DASHBOARD_ONLY=1
            APPLY_RUNTIME=0
            shift
            ;;
        --open)
            OPEN_DASHBOARD=1
            shift
            ;;
        --no-open)
            OPEN_DASHBOARD=0
            shift
            ;;
        --no-dashboard)
            START_DASHBOARD=0
            shift
            ;;
        --current-space)
            CURRENT_SPACE_ONLY=1
            shift
            ;;
        --status)
            print_status
            exit 0
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

if [[ "$DASHBOARD_ONLY" -eq 1 ]]; then
    write_assets
    start_dashboard
    exit 0
fi

if [[ "$APPLY_RUNTIME" -eq 1 ]]; then
    apply_runtime
else
    write_assets
fi

log "Industrial Mac preset applied"
print_status
