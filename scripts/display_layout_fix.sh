#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$SCRIPT_DIR/lib/common.sh"

ROOT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/cento"
STATE_FILE="$CONFIG_DIR/display.env"
LOG_DIR="$ROOT_DIR/logs/display-layout-fix"
LOG_FILE="$LOG_DIR/$(date '+%Y%m%d-%H%M%S')-display-layout-fix.log"
TOP_OUTPUT=""
BOTTOM_OUTPUT=""
SHOW_ONLY=0
SAVE_DEFAULTS=0
REAPPLY_WALLPAPER=1
RELAUNCH_POLYBAR=1

usage() {
    cat <<'USAGE'
Usage: display_layout_fix.sh [options]

Options:
  --top OUTPUT         Force which output is the top monitor
  --bottom OUTPUT      Force which output is the bottom monitor
  --show               Print detected layout info without applying it
  --save-defaults      Save chosen top/bottom outputs to ~/.config/cento/display.env
  --no-wallpaper       Skip wallpaper reapply after layout fix
  --no-polybar         Skip polybar relaunch after layout fix
  -h, --help           Show this help
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

ensure_state_dir() {
    cento_ensure_dir "$CONFIG_DIR"
}

load_state() {
    ensure_state_dir
    if [[ -f "$STATE_FILE" ]]; then
        # shellcheck disable=SC1090
        source "$STATE_FILE"
    fi

    TOP_OUTPUT=${TOP_OUTPUT:-${CENTO_DISPLAY_TOP:-}}
    BOTTOM_OUTPUT=${BOTTOM_OUTPUT:-${CENTO_DISPLAY_BOTTOM:-}}
}

save_state() {
    ensure_state_dir
    cat > "$STATE_FILE" <<EOFSTATE
CENTO_DISPLAY_TOP=$(printf '%q' "$TOP_OUTPUT")
CENTO_DISPLAY_BOTTOM=$(printf '%q' "$BOTTOM_OUTPUT")
EOFSTATE
    log "Saved defaults to $STATE_FILE"
}

read_xrandr_json() {
    python3 - <<'PY'
import json
import re
import subprocess

text = subprocess.check_output(['xrandr', '--query'], text=True)
out = []
for line in text.splitlines():
    m = re.match(r'^(\S+) connected( primary)?(?: ([0-9]+x[0-9]+)\+([0-9]+)\+([0-9]+))?', line)
    if not m:
        continue
    name = m.group(1)
    primary = bool(m.group(2))
    current = m.group(3)
    x = int(m.group(4)) if m.group(4) else None
    y = int(m.group(5)) if m.group(5) else None
    modes = []
    preferred = None
    current_mode = None
    continue_modes = False
    out.append({
        'name': name,
        'primary': primary,
        'current_mode': current,
        'x': x,
        'y': y,
        'modes': modes,
        'preferred_mode': None,
    })
    continue_modes = True

# second pass for modes
current = None
for line in text.splitlines():
    m = re.match(r'^(\S+) connected( primary)?(?: ([0-9]+x[0-9]+)\+([0-9]+)\+([0-9]+))?', line)
    if m:
        name = m.group(1)
        current = next((item for item in out if item['name'] == name), None)
        continue
    if current is None:
        continue
    mm = re.match(r'^\s+([0-9]+x[0-9]+)\s+(.+)$', line)
    if not mm:
        continue
    mode = mm.group(1)
    flags = mm.group(2)
    current['modes'].append(mode)
    if '*' in flags:
        current['current_mode'] = mode
    if '+' in flags and current['preferred_mode'] is None:
        current['preferred_mode'] = mode
print(json.dumps(out))
PY
}

pick_outputs() {
    local json=$1
    mapfile -t parsed < <(python3 - <<'PY' "$json" "$TOP_OUTPUT" "$BOTTOM_OUTPUT"
import json, sys
outputs = json.loads(sys.argv[1])
forced_top = sys.argv[2]
forced_bottom = sys.argv[3]
if len(outputs) < 2:
    raise SystemExit('need at least 2 connected outputs')
if forced_top and not any(o['name'] == forced_top for o in outputs):
    raise SystemExit(f'top output not connected: {forced_top}')
if forced_bottom and not any(o['name'] == forced_bottom for o in outputs):
    raise SystemExit(f'bottom output not connected: {forced_bottom}')
if forced_top and forced_bottom and forced_top == forced_bottom:
    raise SystemExit('top and bottom outputs must differ')
if not forced_top:
    primary = next((o for o in outputs if o['primary']), None)
    forced_top = primary['name'] if primary else outputs[0]['name']
if not forced_bottom:
    forced_bottom = next(o['name'] for o in outputs if o['name'] != forced_top)
for name in (forced_top, forced_bottom):
    output = next(o for o in outputs if o['name'] == name)
    mode = output['current_mode'] or output['preferred_mode'] or (output['modes'][0] if output['modes'] else '')
    width, height = map(int, mode.split('x'))
    print(name)
    print(mode)
    print(width)
    print(height)
PY
)
    TOP_OUTPUT=${parsed[0]}
    TOP_MODE=${parsed[1]}
    TOP_WIDTH=${parsed[2]}
    TOP_HEIGHT=${parsed[3]}
    BOTTOM_OUTPUT=${parsed[4]}
    BOTTOM_MODE=${parsed[5]}
    BOTTOM_WIDTH=${parsed[6]}
    BOTTOM_HEIGHT=${parsed[7]}
}

compute_positions() {
    if (( TOP_WIDTH >= BOTTOM_WIDTH )); then
        TOP_X=0
        BOTTOM_X=$(( (TOP_WIDTH - BOTTOM_WIDTH) / 2 ))
    else
        TOP_X=$(( (BOTTOM_WIDTH - TOP_WIDTH) / 2 ))
        BOTTOM_X=0
    fi
    TOP_Y=0
    BOTTOM_Y=$TOP_HEIGHT
}

apply_layout() {
    log "Applying vertical layout: $TOP_OUTPUT above $BOTTOM_OUTPUT"
    log "Top: mode=$TOP_MODE pos=${TOP_X}x${TOP_Y}"
    log "Bottom: mode=$BOTTOM_MODE pos=${BOTTOM_X}x${BOTTOM_Y}"
    xrandr \
        --output "$TOP_OUTPUT" --primary --mode "$TOP_MODE" --pos "${TOP_X}x${TOP_Y}" \
        --output "$BOTTOM_OUTPUT" --mode "$BOTTOM_MODE" --pos "${BOTTOM_X}x${BOTTOM_Y}"
}

post_refresh() {
    if [[ "$REAPPLY_WALLPAPER" -eq 1 && -x "$HOME/bin/cento" ]]; then
        log "Reapplying wallpaper after xrandr layout change"
        "$HOME/bin/cento" wallpaper-manager --apply-current >/dev/null 2>&1 || cento_warn "Wallpaper reapply failed"
    fi

    if [[ "$RELAUNCH_POLYBAR" -eq 1 && -x "$HOME/.config/polybar/launch.sh" ]]; then
        log "Relaunching polybar"
        "$HOME/.config/polybar/launch.sh" >/dev/null 2>&1 || cento_warn "Polybar relaunch failed"
    fi
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --top)
            TOP_OUTPUT=$2
            shift 2
            ;;
        --bottom)
            BOTTOM_OUTPUT=$2
            shift 2
            ;;
        --show)
            SHOW_ONLY=1
            shift
            ;;
        --save-defaults)
            SAVE_DEFAULTS=1
            shift
            ;;
        --no-wallpaper)
            REAPPLY_WALLPAPER=0
            shift
            ;;
        --no-polybar)
            RELAUNCH_POLYBAR=0
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
cento_require_cmd xrandr
cento_require_cmd python3
load_state
XRANDR_JSON=$(read_xrandr_json)
pick_outputs "$XRANDR_JSON"
compute_positions

printf 'top=%s mode=%s pos=%sx%s\n' "$TOP_OUTPUT" "$TOP_MODE" "$TOP_X" "$TOP_Y"
printf 'bottom=%s mode=%s pos=%sx%s\n' "$BOTTOM_OUTPUT" "$BOTTOM_MODE" "$BOTTOM_X" "$BOTTOM_Y"

if [[ "$SAVE_DEFAULTS" -eq 1 ]]; then
    save_state
fi

if [[ "$SHOW_ONLY" -eq 1 ]]; then
    exit 0
fi

apply_layout
post_refresh
