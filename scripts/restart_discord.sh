#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$SCRIPT_DIR/lib/common.sh"

usage() {
    cat <<'USAGE'
Usage:
  restart_discord.sh rerun
  restart_discord.sh update [--rerun]
  restart_discord.sh status

Restart Discord, install the latest official Linux tarball into the user
profile, or show the current launcher/process state.

Cento commands:
  cento discord rerun
  cento discord update
  cento discord update --rerun
  cento discord status
  cento rd
USAGE
}

ACTION=${1:-rerun}
if [[ $# -gt 0 ]]; then
    shift
fi

case "$ACTION" in
    -h|--help)
        usage
        exit 0
        ;;
    restart)
        ACTION=rerun
        ;;
esac

DISCORD_DOWNLOAD_URL=${CENTO_DISCORD_DOWNLOAD_URL:-https://discord.com/api/download?platform=linux&format=tar.gz}
DISCORD_UPDATES_URL=${CENTO_DISCORD_UPDATES_URL:-https://updates.discord.com/}
DISCORD_INSTALL_DIR=${CENTO_DISCORD_HOME:-$HOME/.local/opt/Discord}
DISCORD_CONFIG_DIR=${CENTO_DISCORD_CONFIG_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/discord}
DISCORD_LOG_DIR=${CENTO_DISCORD_LOG_DIR:-$SCRIPT_DIR/../workspace/runs/discord}
DISCORD_START_WAIT=${CENTO_DISCORD_START_WAIT:-5}

require_linux() {
    [[ "$(uname -s)" == "Linux" ]] || cento_die "Discord control is only supported on Linux."
}

discord_pids() {
    {
        pgrep -x Discord 2>/dev/null || true
        pgrep -x discord 2>/dev/null || true
        pgrep -f 'app/com\.discordapp\.Discord|com\.discordapp\.Discord' 2>/dev/null || true
        pgrep -f '/discord/updater_bootstrap|/Discord/updater_bootstrap' 2>/dev/null || true
        pgrep -f 'zenity --progress --text=Downloading Discord' 2>/dev/null || true
    } | sort -u
}

discord_running() {
    discord_pids | grep -q .
}

discord_app_pids() {
    {
        pgrep -x Discord 2>/dev/null || true
        pgrep -f 'app/com\.discordapp\.Discord|com\.discordapp\.Discord' 2>/dev/null || true
    } | sort -u
}

discord_app_running() {
    discord_app_pids | grep -q .
}

stop_discord() {
    if ! discord_running; then
        cento_info "Discord is not running."
        return 0
    fi

    local pids
    pids=$(discord_pids | tr '\n' ' ')
    cento_info "Stopping Discord..."
    # Prefer exact process-name matches. Broad -f matching can hit the wrapper.
    kill $pids 2>/dev/null || true
    sleep 2

    if discord_running; then
        cento_warn "Discord did not exit after 2s; killing remaining processes."
        pids=$(discord_pids | tr '\n' ' ')
        kill -9 $pids 2>/dev/null || true
        sleep 1
    fi
}

launch_user_local_discord() {
    local log_file=$1
    local executable
    executable=$(prepare_user_local_discord "$log_file") || return 1
    cento_info "Starting Discord from $executable"
    setsid "$executable" --no-sandbox >"$log_file" 2>&1 < /dev/null &
    return 0
}

launch_system_discord() {
    local log_file=$1
    if cento_have_cmd discord; then
        cento_info "Starting Discord with $(command -v discord)"
        setsid discord >"$log_file" 2>&1 < /dev/null &
    elif cento_have_cmd Discord; then
        cento_info "Starting Discord with $(command -v Discord)"
        setsid Discord >"$log_file" 2>&1 < /dev/null &
    elif cento_have_cmd flatpak && flatpak info com.discordapp.Discord >/dev/null 2>&1; then
        cento_info "Starting Discord with Flatpak"
        setsid flatpak run com.discordapp.Discord >"$log_file" 2>&1 < /dev/null &
    elif cento_have_cmd snap && snap list discord >/dev/null 2>&1; then
        cento_info "Starting Discord with Snap"
        setsid snap run discord >"$log_file" 2>&1 < /dev/null &
    else
        return 1
    fi
}

latest_log_path() {
    cento_ensure_dir "$DISCORD_LOG_DIR"
    printf '%s/rerun-%s.log\n' "$DISCORD_LOG_DIR" "$(cento_timestamp)"
}

wait_for_discord() {
    local log_file=$1
    sleep "$DISCORD_START_WAIT"
    if discord_app_running; then
        cento_info "Discord is running."
        discord_app_pids | sed 's/^/[INFO] pid: /' >&2
        return 0
    fi

    cento_warn "Discord did not stay running after ${DISCORD_START_WAIT}s."
    if [[ -f "$log_file" ]] && grep -Eiq 'update-manually|Host update is available|Manual update required' "$log_file"; then
        cento_warn "Installed Discord host is out of date. Run: cento discord update"
    fi
    cento_warn "Log: $log_file"
    [[ -f "$log_file" ]] && tail -40 "$log_file" >&2
    return 1
}

launch_discord() {
    local log_file
    log_file=$(latest_log_path)
    cento_info "Starting Discord..."

    if ! launch_user_local_discord "$log_file"; then
        launch_system_discord "$log_file" || cento_die "Could not find a Discord launcher. Run: cento discord update"
    fi

    wait_for_discord "$log_file"
}

print_status() {
    local executable
    if discord_app_running; then
        printf 'running: yes\n'
        discord_app_pids | sed 's/^/pid: /'
    elif discord_running; then
        printf 'running: bootstrap-only\n'
        discord_pids | sed 's/^/pid: /'
    else
        printf 'running: no\n'
    fi

    if executable=$(user_local_executable); then
        printf 'user_local: %s\n' "$executable"
    else
        printf 'user_local: missing (%s)\n' "$DISCORD_INSTALL_DIR"
    fi

    if cento_have_cmd discord; then
        printf 'system_launcher: %s\n' "$(command -v discord)"
    else
        printf 'system_launcher: missing\n'
    fi
}

user_local_executable() {
    local executable
    if executable=$(user_local_host); then
        printf '%s\n' "$executable"
    elif executable=$(user_local_wrapper); then
        printf '%s\n' "$executable"
    else
        return 1
    fi
}

user_local_wrapper() {
    if [[ -x "$DISCORD_INSTALL_DIR/discord" ]]; then
        printf '%s\n' "$DISCORD_INSTALL_DIR/discord"
    elif [[ -x "$DISCORD_INSTALL_DIR/Discord" ]]; then
        printf '%s\n' "$DISCORD_INSTALL_DIR/Discord"
    else
        return 1
    fi
}

user_local_host() {
    local host
    if [[ -x "$DISCORD_CONFIG_DIR/Discord" ]]; then
        printf '%s\n' "$DISCORD_CONFIG_DIR/Discord"
        return 0
    fi
    host=$(find "$DISCORD_CONFIG_DIR" -maxdepth 2 -type f -name Discord -perm -111 2>/dev/null | sort -V | tail -1)
    if [[ -n "$host" ]]; then
        printf '%s\n' "$host"
        return 0
    fi
    return 1
}

prepare_user_local_discord() {
    local log_file=$1
    local executable
    if executable=$(user_local_host); then
        printf '%s\n' "$executable"
        return 0
    fi
    user_local_wrapper >/dev/null || return 1
    if [[ -x "$DISCORD_INSTALL_DIR/updater_bootstrap" ]]; then
        cento_info "Bootstrapping Discord host without zenity..."
        cento_ensure_dir "$DISCORD_CONFIG_DIR"
        if "$DISCORD_INSTALL_DIR/updater_bootstrap" --no-zenity "$DISCORD_CONFIG_DIR" stable "$DISCORD_UPDATES_URL" >>"$log_file" 2>&1; then
            if executable=$(user_local_host); then
                printf '%s\n' "$executable"
                return 0
            fi
        fi
        cento_warn "Discord bootstrap did not produce a host executable. Log: $log_file"
    fi
    return 1
}
installed_version() {
    local dir=$1
    python3 - "$dir" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
for rel in ("resources/build_info.json", "resources/app/package.json"):
    path = root / rel
    if not path.exists():
        continue
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        continue
    value = data.get("version") or data.get("buildNumber")
    if value:
        print(value)
        raise SystemExit(0)
raise SystemExit(0)
PY
}

update_discord() {
    require_linux
    cento_require_cmd curl
    cento_require_cmd tar
    cento_require_cmd python3

    local parent tmp archive extracted backup version
    parent=$(dirname -- "$DISCORD_INSTALL_DIR")
    cento_ensure_dir "$parent"
    tmp=$(mktemp -d "$parent/discord-update.XXXXXX")
    trap 'if [[ -n "${tmp:-}" && -d "$tmp" ]]; then rm -rf "$tmp"; fi' RETURN
    archive="$tmp/discord.tar.gz"

    cento_info "Downloading latest Discord Linux tarball..."
    curl -fL --retry 2 --connect-timeout 20 -o "$archive" "$DISCORD_DOWNLOAD_URL"

    cento_info "Extracting Discord..."
    tar -xzf "$archive" -C "$tmp"
    extracted="$tmp/Discord"
    if [[ ! -x "$extracted/Discord" && ! -x "$extracted/discord" ]]; then
        cento_die "Downloaded archive did not contain executable Discord/Discord or Discord/discord"
    fi

    version=$(installed_version "$extracted")
    backup=""
    if [[ -e "$DISCORD_INSTALL_DIR" ]]; then
        backup="$parent/Discord.previous.$(cento_timestamp)"
        mv "$DISCORD_INSTALL_DIR" "$backup"
    fi
    mv "$extracted" "$DISCORD_INSTALL_DIR"
    chmod +x "$DISCORD_INSTALL_DIR/Discord" "$DISCORD_INSTALL_DIR/discord" 2>/dev/null || true
    rm -rf "$tmp"
    tmp=""
    trap - RETURN

    cento_info "Installed Discord ${version:-latest} to $DISCORD_INSTALL_DIR"
    if [[ -n "$backup" ]]; then
        cento_info "Previous user-local Discord moved to $backup"
    fi
}

rerun_discord() {
    require_linux
    stop_discord
    launch_discord
}

case "$ACTION" in
    rerun)
        [[ $# -eq 0 ]] || cento_die "Usage: restart_discord.sh rerun"
        rerun_discord
        ;;
    update)
        rerun_after_update=0
        while [[ $# -gt 0 ]]; do
            case "$1" in
                --rerun)
                    rerun_after_update=1
                    shift
                    ;;
                *)
                    cento_die "Usage: restart_discord.sh update [--rerun]"
                    ;;
            esac
        done
        update_discord
        if [[ "$rerun_after_update" -eq 1 ]]; then
            rerun_discord
        fi
        ;;
    status)
        [[ $# -eq 0 ]] || cento_die "Usage: restart_discord.sh status"
        print_status
        ;;
    *)
        cento_die "Unknown action: $ACTION"
        ;;
esac
