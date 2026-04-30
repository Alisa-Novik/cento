#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$SCRIPT_DIR/lib/common.sh"

ROOT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
CONFIG_ROOT="${XDG_CONFIG_HOME:-$HOME/.config}/cento"
DATA_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}/cento/industrial-os"
STATE_ROOT="${XDG_STATE_HOME:-$HOME/.local/state}/cento/industrial-os"
LOG_DIR="$ROOT_DIR/logs/industrial-os"
LOG_FILE="$LOG_DIR/$(date '+%Y%m%d-%H%M%S')-industrial-os.log"
PRESET_ENV="$CONFIG_ROOT/preset.env"
I3_CONFIG=${I3_CONFIG:-$HOME/.config/i3/config}
KITTY_THEME="Cento Industrial OS"
WALLPAPER_FILE="$DATA_ROOT/wallpaper.png"
POLYBAR_DIR="$CONFIG_ROOT/industrial-os/polybar"
POLYBAR_CONFIG="$POLYBAR_DIR/config.ini"
POLYBAR_LAUNCH="$POLYBAR_DIR/launch.sh"
ROFI_THEME="$CONFIG_ROOT/industrial-os/rofi.rasi"
PICOM_CONFIG="$CONFIG_ROOT/industrial-os/picom.conf"
DASHBOARD_HOST=${CENTO_INDUSTRIAL_DASHBOARD_HOST:-127.0.0.1}
DASHBOARD_PORT=${CENTO_INDUSTRIAL_DASHBOARD_PORT:-46268}
DASHBOARD_PID_FILE="$STATE_ROOT/dashboard.pid"
DASHBOARD_URL_FILE="$STATE_ROOT/dashboard.url"
DASHBOARD_PROCESS_LOG="$STATE_ROOT/dashboard.log"
I3_BLOCK_START="# BEGIN_CENTO_INDUSTRIAL_OS"
I3_BLOCK_END="# END_CENTO_INDUSTRIAL_OS"
SESSION_ONLY=0
DASHBOARD_ONLY=0
WORKSPACE_ONLY=0
OPEN_DASHBOARD=0
START_DASHBOARD=1
RELOAD_I3=1
APPLY_RUNTIME=1
WORKSPACE_BACKGROUND_ARGS=()

usage() {
    cat <<'USAGE'
Usage: cento preset industrial-os [options]

Options:
  --session          Apply runtime pieces only; intended for i3 startup.
  --workspace        Compose workspace 1 into the Industrial OS tiled cockpit.
  --backgrounds images|black
                     Use pane images or plain black backgrounds with --workspace.
  --black-only       Alias for --backgrounds black with --workspace.
  --dashboard-only   Start or reuse the themed dashboard server only.
  --open             Open the themed dashboard after starting it.
  --no-open          Do not open the themed dashboard.
  --no-dashboard     Do not start the dashboard server.
  --no-reload        Do not reload i3 after writing the managed block.
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
CENTO_PRESET=industrial-os
CENTO_PRESET_NAME=$(printf '%q' "Industrial OS")
CENTO_PRESET_APPLIED_AT=$(printf '%q' "$(date --iso-8601=seconds)")
CENTO_WALLPAPER=$(printf '%q' "$WALLPAPER_FILE")
CENTO_POLYBAR_CONFIG=$(printf '%q' "$POLYBAR_CONFIG")
CENTO_ROFI_THEME=$(printf '%q' "$ROFI_THEME")
CENTO_DASHBOARD_THEME=industrial
EOF_STATE
}

generate_wallpaper() {
    if [[ -f "$WALLPAPER_FILE" ]]; then
        return 0
    fi

    cento_ensure_dir "$DATA_ROOT"
    python3 - "$WALLPAPER_FILE" <<'PY'
from __future__ import annotations

import math
import struct
import sys
import zlib
from pathlib import Path

path = Path(sys.argv[1])
width, height = 2560, 1440


def clamp(value: float) -> int:
    return max(0, min(255, int(value)))


def chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


rows = []
for y in range(height):
    row = bytearray([0])
    fy = y / (height - 1)
    for x in range(width):
        fx = x / (width - 1)
        base = 5 + 18 * (1 - fy)
        smoke = 16 * max(0, math.sin(fx * 21 + fy * 8) * math.sin(fx * 5 - fy * 19))
        glow = max(0, 1 - ((fx - 0.50) ** 2 / 0.055 + (fy - 0.32) ** 2 / 0.035))
        horizon = max(0, 1 - abs(fy - 0.58) / 0.18)
        r = base + smoke + 180 * glow + 42 * horizon
        g = base * 0.58 + 54 * glow + 12 * horizon
        b = base * 0.44 + 10 * glow

        cone_left = 0.36 + 0.22 * fy
        cone_right = 0.64 - 0.22 * fy
        if 0.27 < fy < 0.78 and cone_left < fx < cone_right:
            shade = 20 + 30 * (fy - 0.27)
            lava = max(0, 1 - abs(fx - 0.50) / (0.012 + 0.04 * fy))
            r = max(r, shade + 220 * lava)
            g = max(g, 10 + 70 * lava)
            b = min(b, 22)

        if fy > 0.60:
            band = int((fx * 42) % 1 < 0.035)
            r = max(r, 16 + band * 55)
            g = max(g, 9 + band * 18)
            b = max(b, 7 + band * 8)

        for cx, top, w, hot in ((0.18, 0.53, 0.055, 0.7), (0.74, 0.47, 0.07, 1.0), (0.82, 0.39, 0.032, 0.9)):
            if abs(fx - cx) < w and fy > top:
                r = max(r, 24 + 65 * hot)
                g = max(g, 15 + 22 * hot)
                b = max(b, 12)
            if abs(fx - cx) < w * 0.22 and fy > top - 0.20:
                r = max(r, 58 + 70 * hot)
                g = max(g, 26 + 20 * hot)
                b = max(b, 14)

        if fy > 0.83:
            r *= 0.55
            g *= 0.50
            b *= 0.48
            if int(fx * 96) % 9 == 0:
                r = max(r, 75)
                g = max(g, 26)

        noise = math.sin((x * 12.9898 + y * 78.233) * 0.05) * 7
        row.extend((clamp(r + noise), clamp(g + noise * 0.4), clamp(b + noise * 0.2)))
    rows.append(bytes(row))

raw = b"".join(rows)
png = b"\x89PNG\r\n\x1a\n"
png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
png += chunk(b"IDAT", zlib.compress(raw, 6))
png += chunk(b"IEND", b"")
path.write_bytes(png)
PY
    log "Generated wallpaper: $WALLPAPER_FILE"
}

write_rofi_theme() {
    cento_ensure_dir "$(dirname "$ROFI_THEME")"
    cat > "$ROFI_THEME" <<'EOF_ROFI'
configuration {
    dpi: 120;
}

* {
    font: "FiraCode Nerd Font 16";
    background: #050403ee;
    foreground: #f4e8dc;
    muted: #a88b78;
    accent: #ff5a00;
    warning: #ffb000;
}

window {
    transparency: "real";
    background-color: @background;
    border: 1px;
    border-color: @accent;
    border-radius: 4px;
    padding: 16px;
}

mainbox {
    spacing: 10px;
}

inputbar {
    padding: 10px 12px;
    background-color: #130b07;
    text-color: @foreground;
    border: 1px;
    border-color: #5a210d;
}

prompt {
    text-color: @accent;
}

element {
    padding: 7px 10px;
    spacing: 8px;
    text-color: @foreground;
}

element selected {
    background-color: #ff5a00;
    text-color: #050403;
}

scrollbar {
    width: 6px;
    handle-color: @accent;
    background-color: #130b07;
}
EOF_ROFI
}

write_picom_config() {
    cento_ensure_dir "$(dirname "$PICOM_CONFIG")"
    cat > "$PICOM_CONFIG" <<'EOF_PICOM'
backend = "glx";
vsync = true;
xrender-sync-fence = true;
use-damage = false;
opacity-rule = [
  "84:class_g = 'kitty'",
  "92:class_g = 'Rofi'"
];
blur-method = "dual_kawase";
blur-strength = 6;
corner-radius = 2;
detect-rounded-corners = true;
EOF_PICOM
}

write_polybar_assets() {
    cento_ensure_dir "$POLYBAR_DIR"
    cat > "$POLYBAR_CONFIG" <<EOF_POLYBAR
[colors]
background = #ee050403
background-alt = #ff130b07
foreground = #f4e8dc
muted = #a88b78
border = #5a210d
accent = #ff5a00
accent-alt = #ff9a3d
ok = #6be675
warn = #ffb000
bad = #ff3500

[bar/main]
monitor = \${env:MONITOR:}
override-redirect = false
bottom = false
fixed-center = true
width = 100%
height = 38
offset-x = 0
offset-y = 0
background = \${colors.background}
foreground = \${colors.foreground}
border-bottom-size = 1
border-bottom-color = \${colors.border}
padding-left = 1
padding-right = 1
module-margin-left = 1
module-margin-right = 1
font-0 = "FiraCode Nerd Font:size=12;3"
font-1 = "monospace:size=12;3"
modules-left = os workspaces
modules-center = date
modules-right = jobs status volume power
separator =
wm-restack = i3
enable-ipc = true
cursor-click = pointer

[module/os]
type = custom/text
content = " INDUSTRIAL OS "
content-foreground = \${colors.accent}
click-left = $HOME/bin/cento preset industrial-os --dashboard-only --open &

[module/workspaces]
type = internal/xworkspaces
pin-workspaces = true
enable-click = true
enable-scroll = true
label-active = " %name% "
label-active-foreground = #050403
label-active-background = \${colors.accent}
label-occupied = " %name% "
label-occupied-foreground = \${colors.foreground}
label-empty = " %name% "
label-empty-foreground = \${colors.muted}
label-urgent = " %name% "
label-urgent-foreground = #050403
label-urgent-background = \${colors.bad}

[module/date]
type = internal/date
interval = 1
date = %A, %d %B
time = at %I:%M %p
label = %date% %time%
format-foreground = \${colors.foreground}

[module/jobs]
type = custom/script
exec = python3 "$ROOT_DIR/scripts/industrial_status.py" --jobs
interval = 20
format-foreground = \${colors.accent-alt}
click-left = $HOME/bin/cento preset industrial-os --dashboard-only --open &

[module/status]
type = custom/script
exec = python3 "$ROOT_DIR/scripts/industrial_status.py" --polybar
interval = 5
format-foreground = \${colors.foreground}

[module/volume]
type = internal/pulseaudio
interval = 5
format-volume = VOL <label-volume>
label-volume = %percentage%%
format-muted = VOL muted
format-muted-foreground = \${colors.bad}

[module/power]
type = custom/text
content = " PWR "
content-foreground = \${colors.accent}
click-left = i3-nagbar -t warning -m 'Power action' -B 'lock' 'i3lock -c 050403' -B 'reboot' 'systemctl reboot' -B 'poweroff' 'systemctl poweroff' &

[settings]
screenchange-reload = true
pseudo-transparency = false
EOF_POLYBAR

    cat > "$POLYBAR_LAUNCH" <<EOF_LAUNCH
#!/usr/bin/env bash
set -euo pipefail
DIR="$POLYBAR_DIR"
killall -q polybar 2>/dev/null || true
while pgrep -u "\$UID" -x polybar >/dev/null; do sleep 0.2; done
: > /tmp/cento-industrial-polybar.log
polybar -m | cut -d: -f1 | while read -r monitor; do
    [[ -n "\$monitor" ]] || continue
    MONITOR="\$monitor" setsid -f polybar main -c "\$DIR/config.ini" </dev/null >>/tmp/cento-industrial-polybar.log 2>&1
done
EOF_LAUNCH
    chmod +x "$POLYBAR_LAUNCH"
}

write_i3_block() {
    [[ -f "$I3_CONFIG" ]] || cento_die "i3 config not found: $I3_CONFIG"
    local block_file="$STATE_ROOT/i3-block"
    cento_ensure_dir "$STATE_ROOT"
    cat > "$block_file" <<EOF_I3
$I3_BLOCK_START
# Managed by cento preset industrial-os.
font pango:FiraCode Nerd Font 8
gaps inner 3
gaps outer 2
smart_gaps on
hide_edge_borders none
new_window pixel 3
new_float pixel 3
client.focused #ffb000 #ff5a00 #050403 #ffd166 #ffb000
client.focused_inactive #6a260e #130b07 #c4a28e #6a260e #6a260e
client.unfocused #24110a #090705 #8a6a5a #24110a #24110a
client.urgent #ff3500 #ff3500 #050403 #ff3500 #ff3500
client.placeholder #5a210d #050403 #a88b78 #5a210d #5a210d
client.background #050403
exec_always --no-startup-id $HOME/bin/cento preset industrial-os --session
bindsym \$mod+Shift+i exec --no-startup-id $HOME/bin/cento preset industrial-os --workspace
bindsym \$mod+Shift+u exec --no-startup-id $HOME/bin/cento preset industrial-os --session
bindsym \$mod+Shift+o exec --no-startup-id $HOME/bin/cento preset industrial-os --dashboard-only --open
bindsym \$mod+Shift+Space exec --no-startup-id rofi -modi drun,run -show drun -theme $ROFI_THEME
$I3_BLOCK_END
EOF_I3

    I3_CONFIG_PATH="$I3_CONFIG" BLOCK_FILE="$block_file" ROOT_DIR="$ROOT_DIR" python3 - <<'PY'
import os
import re
from pathlib import Path

path = Path(os.environ["I3_CONFIG_PATH"])
block = Path(os.environ["BLOCK_FILE"]).read_text(encoding="utf-8").rstrip() + "\n"
root_dir = Path(os.environ["ROOT_DIR"])
text = path.read_text(encoding="utf-8")
pattern = re.compile(r"(?ms)^# BEGIN_CENTO_INDUSTRIAL_OS\n.*?^# END_CENTO_INDUSTRIAL_OS\n?")
if pattern.search(text):
    text = pattern.sub(block, text)
else:
    if text and not text.endswith("\n"):
        text += "\n"
    text += "\n" + block

focus_script = root_dir / "scripts" / "industrial_focus.py"
for key, direction in {"h": "left", "j": "down", "k": "up", "l": "right"}.items():
    binding = f"bindsym $mod+{key} exec --no-startup-id {focus_script} {direction}"
    key_pattern = re.compile(rf"(?m)^bindsym \$mod\+{key}\s+.*$")
    if key_pattern.search(text):
        text = key_pattern.sub(binding, text)
    else:
        text = text.replace(block, binding + "\n" + block)
path.write_text(text, encoding="utf-8")
PY
    log "Updated i3 preset block: $I3_CONFIG"
}

apply_kitty_theme() {
    if [[ -x "$HOME/bin/cento" ]]; then
        "$HOME/bin/cento" kitty-theme-manager --theme "$KITTY_THEME" || cento_warn "Kitty theme apply failed"
    else
        "$ROOT_DIR/scripts/kitty_theme_manager.sh" --theme "$KITTY_THEME" || cento_warn "Kitty theme apply failed"
    fi
}

apply_wallpaper() {
    cento_require_cmd feh
    feh --bg-fill "$WALLPAPER_FILE"
    cat > "$CONFIG_ROOT/wallpaper.env" <<EOF_WALLPAPER
WALLPAPER_LIBRARY_DIR=$(printf '%q' "$DATA_ROOT")
CURRENT_WALLPAPER=$(printf '%q' "$WALLPAPER_FILE")
WALLPAPER_MODE=--bg-fill
EOF_WALLPAPER
    log "Applied wallpaper: $WALLPAPER_FILE"
}

launch_polybar() {
    cento_require_cmd polybar
    "$POLYBAR_LAUNCH"
    log "Launched Industrial OS Polybar"
}

launch_picom() {
    if ! cento_have_cmd picom; then
        cento_warn "picom is not installed; skipping compositor refresh"
        return 0
    fi
    pkill -x picom >/dev/null 2>&1 || true
    sleep 0.2
    picom --config "$PICOM_CONFIG" --daemon >/dev/null 2>&1 || cento_warn "Failed to start picom with $PICOM_CONFIG"
}

dashboard_alive() {
    local pid
    [[ -f "$DASHBOARD_PID_FILE" ]] || return 1
    pid=$(<"$DASHBOARD_PID_FILE")
    [[ "$pid" =~ ^[0-9]+$ ]] || return 1
    [[ -d "/proc/$pid" ]] || return 1
    tr '\0' ' ' < "/proc/$pid/cmdline" | grep -Fq "dashboard_server.py" || return 1
    tr '\0' ' ' < "/proc/$pid/cmdline" | grep -Fq -- "--theme industrial" || return 1
}

open_dashboard_url() {
    local url=${1:-}
    [[ -n "$url" ]] || return 0
    if [[ "$OPEN_DASHBOARD" -eq 1 ]] && cento_have_cmd xdg-open; then
        xdg-open "$url" >/dev/null 2>&1 || true
    fi
}

start_dashboard() {
    [[ "$START_DASHBOARD" -eq 1 ]] || return 0
    cento_ensure_dir "$STATE_ROOT"
    if dashboard_alive; then
        local existing_url
        existing_url=$(cat "$DASHBOARD_URL_FILE" 2>/dev/null || true)
        [[ -n "$existing_url" ]] || existing_url="http://$DASHBOARD_HOST:$DASHBOARD_PORT"
        log "Industrial dashboard already running: $existing_url"
        open_dashboard_url "$existing_url"
        return 0
    fi

    : > "$DASHBOARD_PROCESS_LOG"
    local -a dashboard_cmd=(
        env CENTO_DASHBOARD_THEME=industrial
        python3 "$ROOT_DIR/scripts/dashboard_server.py"
        --host "$DASHBOARD_HOST"
        --port "$DASHBOARD_PORT"
        --theme industrial
    )
    if cento_have_cmd setsid; then
        nohup setsid "${dashboard_cmd[@]}" > "$DASHBOARD_PROCESS_LOG" 2>&1 &
    else
        nohup "${dashboard_cmd[@]}" > "$DASHBOARD_PROCESS_LOG" 2>&1 &
    fi
    local pid=$!
    echo "$pid" > "$DASHBOARD_PID_FILE"
    disown "$pid" 2>/dev/null || true
    sleep 0.8

    if ! kill -0 "$pid" >/dev/null 2>&1; then
        cat "$DASHBOARD_PROCESS_LOG" >&2 || true
        cento_die "Industrial dashboard failed to stay running"
    fi

    local url
    url=$(grep -Eo 'http://[^ ]+' "$DASHBOARD_PROCESS_LOG" | tail -1 || true)
    [[ -n "$url" ]] || url="http://$DASHBOARD_HOST:$DASHBOARD_PORT"
    printf '%s\n' "$url" > "$DASHBOARD_URL_FILE"
    log "Industrial dashboard running: $url"
    open_dashboard_url "$url"
}

write_assets() {
    cento_require_cmd python3
    generate_wallpaper
    write_rofi_theme
    write_picom_config
    write_polybar_assets
    write_preset_state
}

apply_runtime() {
    write_assets
    apply_kitty_theme
    apply_wallpaper
    launch_picom
    launch_polybar
    start_dashboard
}

print_status() {
    printf 'preset: industrial-os\n'
    printf 'i3 config: %s\n' "$I3_CONFIG"
    printf 'wallpaper: %s\n' "$WALLPAPER_FILE"
    printf 'polybar: %s\n' "$POLYBAR_CONFIG"
    printf 'rofi theme: %s\n' "$ROFI_THEME"
    printf 'picom: %s\n' "$PICOM_CONFIG"
    printf 'preset env: %s\n' "$PRESET_ENV"
    if dashboard_alive; then
        printf 'dashboard: running %s\n' "$(cat "$DASHBOARD_URL_FILE" 2>/dev/null || true)"
    else
        printf 'dashboard: stopped\n'
    fi
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --session)
            SESSION_ONLY=1
            OPEN_DASHBOARD=0
            RELOAD_I3=0
            shift
            ;;
        --workspace)
            WORKSPACE_ONLY=1
            OPEN_DASHBOARD=0
            RELOAD_I3=0
            shift
            ;;
        --backgrounds)
            WORKSPACE_BACKGROUND_ARGS+=(--backgrounds "$2")
            shift 2
            ;;
        --black-only)
            WORKSPACE_BACKGROUND_ARGS+=(--black-only)
            shift
            ;;
        --dashboard-only)
            DASHBOARD_ONLY=1
            APPLY_RUNTIME=0
            RELOAD_I3=0
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
        --no-reload)
            RELOAD_I3=0
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

if [[ "$WORKSPACE_ONLY" -eq 1 ]]; then
    write_assets
    launch_polybar
    exec "$ROOT_DIR/scripts/industrial_workspace.sh" "${WORKSPACE_BACKGROUND_ARGS[@]}"
fi

if [[ "$DASHBOARD_ONLY" -eq 1 ]]; then
    write_assets
    start_dashboard
    exit 0
fi

if [[ "$SESSION_ONLY" -eq 0 ]]; then
    write_assets
    write_i3_block
fi

if [[ "$APPLY_RUNTIME" -eq 1 ]]; then
    apply_runtime
fi

if [[ "$SESSION_ONLY" -eq 0 && "$RELOAD_I3" -eq 1 ]]; then
    if cento_have_cmd i3-msg; then
        i3-msg reload >/dev/null 2>&1 || cento_warn "i3 reload failed"
    else
        cento_warn "i3-msg is not installed; skipping i3 reload"
    fi
fi

log "Industrial OS preset applied"
print_status
