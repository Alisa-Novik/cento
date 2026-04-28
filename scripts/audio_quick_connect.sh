#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$SCRIPT_DIR/lib/common.sh"

ROOT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
LOG_DIR="$ROOT_DIR/logs/audio-quick-connect"
cento_ensure_dir "$LOG_DIR"
LOG_FILE="$LOG_DIR/$(cento_timestamp).log"
ln -sfn "$LOG_FILE" "$LOG_DIR/latest.log"

exec > >(tee -a "$LOG_FILE") 2>&1

usage() {
    cat <<'USAGE'
Usage: audio_quick_connect.sh [DEVICE]

Quickly connect a paired Bluetooth audio device by exact name, substring, or MAC address.
Examples:
  audio_quick_connect.sh "Black Diamond"
  audio_quick_connect.sh "Bose"
USAGE
}

log() {
    printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S %z')" "$*"
}

bt_payload() {
    local payload=$1
    bluetoothctl <<EOF_BT
$payload
quit
EOF_BT
}

resolve_target() {
    local query=$1
    local devices address name lower_query lower_name
    devices=$(bluetoothctl devices Paired)
    lower_query=$(printf '%s' "$query" | tr '[:upper:]' '[:lower:]')

    while IFS= read -r line; do
        [[ $line =~ ^Device[[:space:]]+([0-9A-F:]+)[[:space:]]+(.+)$ ]] || continue
        address=${BASH_REMATCH[1]}
        name=${BASH_REMATCH[2]}
        lower_name=$(printf '%s' "$name" | tr '[:upper:]' '[:lower:]')

        if [[ $address == "$query" || $lower_name == "$lower_query" || $lower_name == *"$lower_query"* ]]; then
            printf '%s|%s\n' "$address" "$name"
            return 0
        fi
    done <<< "$devices"

    return 1
}

verify_audio_device() {
    local address=$1
    local info
    info=$(bluetoothctl info "$address") || return 1
    grep -Eq 'Icon: audio-|UUID: (Audio Sink|Advanced Audio Distribu|Headset|Handsfree)' <<< "$info"
}

connect_device() {
    local address=$1
    bt_payload "power on
agent on
default-agent
trust $address
connect $address"
}

is_connected() {
    local address=$1
    bluetoothctl info "$address" | grep -q '^\s*Connected: yes$'
}

main() {
    local query=${1:-}
    [[ -n $query ]] || {
        usage
        exit 1
    }

    cento_require_cmd bluetoothctl

    local resolved address name result
    resolved=$(resolve_target "$query") || cento_die "No paired Bluetooth device matched: $query"
    address=${resolved%%|*}
    name=${resolved#*|}

    log "Resolved target: $name ($address)"

    if ! verify_audio_device "$address"; then
        cento_die "Matched device is not an audio device: $name ($address)"
    fi

    log "Attempting quick connect"
    result=$(connect_device "$address" || true)
    printf '%s\n' "$result"

    if ! is_connected "$address"; then
        log "First connect attempt did not stick; retrying after a short disconnect"
        bt_payload "disconnect $address"
        sleep 1
        result=$(connect_device "$address" || true)
        printf '%s\n' "$result"
    fi

    if is_connected "$address"; then
        log "Connected: $name ($address)"
        exit 0
    fi

    cento_die "Bluetooth audio device did not stay connected: $name ($address). See $LOG_FILE"
}

main "$@"
