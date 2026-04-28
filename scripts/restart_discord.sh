#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$SCRIPT_DIR/lib/common.sh"

usage() {
    cat <<'USAGE'
Usage: restart_discord.sh

Restart Discord by terminating the current desktop process and launching it
again through the first available launcher: discord, Discord, flatpak, or snap.
USAGE
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            usage
            exit 0
            ;;
        *)
            cento_die "Unknown argument: $1"
            ;;
    esac
done

DISCORD_PROCESS_PATTERN='(^|/)(Discord|discord)( |$)|app/com\.discordapp\.Discord'

discord_running() {
    pgrep -f "$DISCORD_PROCESS_PATTERN" >/dev/null 2>&1
}

stop_discord() {
    if ! discord_running; then
        cento_info "Discord is not running."
        return 0
    fi

    cento_info "Stopping Discord..."
    pkill -TERM -f "$DISCORD_PROCESS_PATTERN" || true
    sleep 2

    if discord_running; then
        cento_warn "Discord did not exit after 2s; killing remaining processes."
        pkill -KILL -f "$DISCORD_PROCESS_PATTERN" || true
    fi
}

launch_discord() {
    cento_info "Starting Discord..."

    if cento_have_cmd discord; then
        setsid discord >/dev/null 2>&1 &
    elif cento_have_cmd Discord; then
        setsid Discord >/dev/null 2>&1 &
    elif cento_have_cmd flatpak && flatpak info com.discordapp.Discord >/dev/null 2>&1; then
        setsid flatpak run com.discordapp.Discord >/dev/null 2>&1 &
    elif cento_have_cmd snap && snap list discord >/dev/null 2>&1; then
        setsid snap run discord >/dev/null 2>&1 &
    else
        cento_die "Could not find a Discord launcher: discord, Discord, flatpak com.discordapp.Discord, or snap discord"
    fi

    cento_info "Discord restart requested."
}

stop_discord
launch_discord
