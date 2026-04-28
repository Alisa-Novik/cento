#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$SCRIPT_DIR/lib/common.sh"

DEFAULT_VM_USER="opc"
DEFAULT_VM_HOST="129.213.17.199"
DEFAULT_VM_IDENTITY="$HOME/.ssh/id_ed25519"
DEFAULT_REMOTE_BIND="127.0.0.1"
DEFAULT_REMOTE_PORT="2222"
DEFAULT_LOCAL_HOST="127.0.0.1"
DEFAULT_LOCAL_PORT="22"
DEFAULT_LOCAL_USER="${CENTO_BRIDGE_TARGET_USER:-alice}"
DEFAULT_REMOTE_CENTO_ROOT='$HOME/projects/cento'
DEFAULT_MAC_USER="${CENTO_BRIDGE_MAC_USER:-anovik-air}"
DEFAULT_MAC_CENTO_ROOT="/Users/anovik-air/cento"
DEFAULT_MAC_SSHD_PORT="22220"
DEFAULT_LINUX_SOCKET="/tmp/cento-linux.sock"
DEFAULT_MAC_SOCKET="/tmp/cento-mac.sock"
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/cento"
PID_FILE="$STATE_DIR/bridge.pid"
LOG_FILE="$STATE_DIR/bridge.log"
MAC_SSHD_DIR="$STATE_DIR/sshd"
MAC_SSHD_CONFIG="$MAC_SSHD_DIR/sshd_config"
MAC_SSHD_PID="$MAC_SSHD_DIR/sshd.pid"

usage() {
    cat <<'USAGE'
Usage: cento bridge <command> [options]

Commands:
  start          Start a background reverse SSH tunnel through the OCI VM
  foreground     Run the reverse SSH tunnel in the foreground
  stop           Stop the background tunnel started by cento bridge
  restart        Stop and start the background tunnel
  status         Show tunnel status and connection commands
  check          Validate local repo and remote Mac-through-VM access
  from-mac       Run a default or provided command on the Linux node from the Mac
  expose-linux   Expose this Linux node on the VM as a Unix socket
  expose-mac     Start user-level Mac sshd and expose this Mac as a VM Unix socket
  to-linux       Open a shell on the Linux node through the VM Unix socket
  to-mac         Open a shell on the Mac node through the VM Unix socket
  context-linux  Print Linux node gather-context through the VM Unix socket
  context-mac    Print Mac node gather-context through the VM Unix socket
  mesh-status    Show VM-side Cento Unix sockets
  command        Print the local tunnel command
  mac-command    Print the Mac command for connecting through the VM
  docs           Print bridge notes

Options:
  --vm-host HOST          OCI VM public IP or hostname (default: 129.213.17.199)
  --vm-user USER          OCI VM SSH user (default: opc)
  --identity PATH         Private key for the OCI VM (default: ~/.ssh/id_ed25519)
  --remote-port PORT      Port opened on the VM side (default: 2222)
  --remote-bind ADDRESS   VM bind address (default: 127.0.0.1)
  --local-host ADDRESS    Local target address (default: 127.0.0.1)
  --local-port PORT       Local target port (default: 22)
  --local-user USER       User Mac should SSH into on the Linux node (default: alice)
  --mac-user USER         User Linux should SSH into on the Mac node (default: anovik-air)
  --public                Bind remote tunnel to 0.0.0.0; requires VM sshd GatewayPorts/firewall
  -h, --help              Show this help

Examples:
  cento bridge start
  cento bridge status
  cento bridge check
  cento bridge expose-linux
  cento bridge expose-mac
  cento bridge to-linux
  cento bridge to-mac
  cento bridge context-linux
  cento bridge context-mac
  cento bridge from-mac
  cento bridge from-mac -- 'cd "$HOME/projects/cento" && ./scripts/cento.sh platforms linux'
  cento bridge mac-command
  cento bridge foreground
USAGE
}

expand_path() {
    local value=$1
    if [[ "$value" == ~* ]]; then
        printf '%s\n' "${value/#\~/$HOME}"
        return
    fi
    printf '%s\n' "$value"
}

quote_words() {
    printf '%q ' "$@"
    printf '\n'
}

is_running() {
    [[ -f "$PID_FILE" ]] || return 1
    local pid
    pid=$(<"$PID_FILE")
    [[ -n "$pid" ]] || return 1
    kill -0 "$pid" >/dev/null 2>&1
}

build_ssh_command() {
    local mode=$1
    shift
    local vm_user=$1 vm_host=$2 identity=$3 remote_bind=$4 remote_port=$5 local_host=$6 local_port=$7
    local -a cmd=(
        ssh
        -N
        -T
        -o ExitOnForwardFailure=yes
        -o ServerAliveInterval=30
        -o ServerAliveCountMax=3
        -i "$identity"
        -R "${remote_bind}:${remote_port}:${local_host}:${local_port}"
        "${vm_user}@${vm_host}"
    )
    if [[ "$mode" == "background" ]]; then
        cmd=(
            ssh
            -N
            -T
            -o BatchMode=yes
            -o ExitOnForwardFailure=yes
            -o ServerAliveInterval=30
            -o ServerAliveCountMax=3
            -i "$identity"
            -R "${remote_bind}:${remote_port}:${local_host}:${local_port}"
            "${vm_user}@${vm_host}"
        )
    fi
    quote_words "${cmd[@]}"
}

print_mac_command() {
    local vm_user=$1 vm_host=$2 remote_port=$3 local_user=$4
    quote_words ssh -J "${vm_user}@${vm_host}" -p "$remote_port" "${local_user}@127.0.0.1"
}

print_status() {
    local vm_user=$1 vm_host=$2 remote_bind=$3 remote_port=$4 local_host=$5 local_port=$6 local_user=$7
    if is_running; then
        printf 'Bridge: running (pid %s)\n' "$(<"$PID_FILE")"
    else
        printf 'Bridge: stopped\n'
    fi
    printf 'VM: %s@%s\n' "$vm_user" "$vm_host"
    printf 'Requested remote tunnel: %s:%s on VM -> this machine %s:%s\n' "$remote_bind" "$remote_port" "$local_host" "$local_port"
    printf 'Mac command: '
    print_mac_command "$vm_user" "$vm_host" "$remote_port" "$local_user"
    printf 'Log: %s\n' "$LOG_FILE"
}

run_check() {
    local vm_user=$1 vm_host=$2 remote_port=$3 local_user=$4
    local repo_dir=${CENTO_ROOT:-$(cd -- "$SCRIPT_DIR/.." && pwd)}

    printf 'Bridge check\n'
    printf 'local_host: %s\n' "$(hostname 2>/dev/null || true)"
    printf 'local_repo: %s\n' "$repo_dir"

    if [[ -d "$repo_dir/.git" ]]; then
        printf 'local_git: '
        git -C "$repo_dir" status --short --branch | head -1
    else
        printf 'local_git: missing\n'
    fi

    printf 'local_cento: '
    if command -v cento >/dev/null 2>&1; then
        command -v cento
    elif [[ -x "$HOME/bin/cento" ]]; then
        printf '%s\n' "$HOME/bin/cento"
    else
        printf 'missing\n'
    fi

    local -a remote_cmd=(
        ssh
        -o BatchMode=yes
        -o StrictHostKeyChecking=accept-new
        -o ConnectTimeout=8
        -J "${vm_user}@${vm_host}"
        -p "$remote_port"
        "${local_user}@127.0.0.1"
        'hostname; test -d "$HOME/projects/cento/.git" && git -C "$HOME/projects/cento" status --short --branch | head -1; if command -v cento >/dev/null 2>&1; then command -v cento; cento --help | head -1; elif test -x "$HOME/bin/cento"; then printf "%s\n" "$HOME/bin/cento"; "$HOME/bin/cento" --help | head -1; else printf "cento missing\n"; exit 1; fi'
    )

    printf 'remote_command: '
    print_mac_command "$vm_user" "$vm_host" "$remote_port" "$local_user"
    printf 'remote_check:\n'
    if "${remote_cmd[@]}"; then
        printf 'remote_status: ok\n'
    else
        printf 'remote_status: failed\n'
        return 1
    fi
}

run_from_mac() {
    local vm_user=$1 vm_host=$2 remote_port=$3 local_user=$4
    shift 4

    local remote_command
    if [[ $# -gt 0 ]]; then
        remote_command="$*"
    else
        remote_command="cd $DEFAULT_REMOTE_CENTO_ROOT && ./scripts/cento.sh gather-context --no-remote | head -90"
    fi

    exec ssh \
        -o StrictHostKeyChecking=accept-new \
        -J "${vm_user}@${vm_host}" \
        -p "$remote_port" \
        "${local_user}@127.0.0.1" \
        "$remote_command"
}

start_mac_sshd() {
    [[ "$(uname -s)" == "Darwin" ]] || cento_die "mac sshd helper must run on macOS"
    cento_ensure_dir "$MAC_SSHD_DIR"
    cento_ensure_dir "$HOME/.ssh"
    chmod 700 "$HOME/.ssh" "$MAC_SSHD_DIR"

    if [[ -n "${CENTO_BRIDGE_AUTHORIZED_KEY:-}" ]]; then
        touch "$HOME/.ssh/authorized_keys"
        grep -qxF "$CENTO_BRIDGE_AUTHORIZED_KEY" "$HOME/.ssh/authorized_keys" || printf '%s\n' "$CENTO_BRIDGE_AUTHORIZED_KEY" >> "$HOME/.ssh/authorized_keys"
        chmod 600 "$HOME/.ssh/authorized_keys"
    fi

    if [[ ! -f "$MAC_SSHD_DIR/ssh_host_ed25519_key" ]]; then
        ssh-keygen -t ed25519 -N '' -f "$MAC_SSHD_DIR/ssh_host_ed25519_key" >/dev/null
    fi

    cat > "$MAC_SSHD_CONFIG" <<EOF_SSHD
Port $DEFAULT_MAC_SSHD_PORT
ListenAddress 127.0.0.1
HostKey $MAC_SSHD_DIR/ssh_host_ed25519_key
PidFile $MAC_SSHD_PID
AuthorizedKeysFile $HOME/.ssh/authorized_keys
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
PermitRootLogin no
AllowTcpForwarding yes
X11Forwarding no
UsePAM no
LogLevel VERBOSE
StrictModes no
EOF_SSHD

    /usr/sbin/sshd -t -f "$MAC_SSHD_CONFIG"
    if [[ -f "$MAC_SSHD_PID" ]] && kill -0 "$(<"$MAC_SSHD_PID")" >/dev/null 2>&1; then
        printf 'Mac user sshd already running (pid %s).\n' "$(<"$MAC_SSHD_PID")"
        return 0
    fi
    /usr/sbin/sshd -f "$MAC_SSHD_CONFIG" -E "$MAC_SSHD_DIR/sshd.log"
    printf 'Mac user sshd started on 127.0.0.1:%s.\n' "$DEFAULT_MAC_SSHD_PORT"
}

start_socket_tunnel() {
    local vm_user=$1 vm_host=$2 socket_path=$3 target_host=$4 target_port=$5 label=$6
    cento_require_cmd ssh
    cento_ensure_dir "$STATE_DIR"
    local pid_file="$STATE_DIR/${label}-socket.pid"
    local log_file="$STATE_DIR/${label}-socket.log"
    if [[ -f "$pid_file" ]] && kill -0 "$(<"$pid_file")" >/dev/null 2>&1; then
        printf '%s socket tunnel already running (pid %s).\n' "$label" "$(<"$pid_file")"
        return 0
    fi
    if ssh -o BatchMode=yes -o ConnectTimeout=5 "${vm_user}@${vm_host}" "test -S '$socket_path'" >/dev/null 2>&1; then
        printf '%s socket already exists on VM: %s\n' "$label" "$socket_path"
        return 0
    fi
    rm -f "$pid_file"
    nohup ssh \
        -N \
        -T \
        -o BatchMode=yes \
        -o ExitOnForwardFailure=yes \
        -o StreamLocalBindUnlink=yes \
        -o ServerAliveInterval=30 \
        -o ServerAliveCountMax=3 \
        -R "${socket_path}:${target_host}:${target_port}" \
        "${vm_user}@${vm_host}" >"$log_file" 2>&1 &
    printf '%s\n' "$!" > "$pid_file"
    sleep 1
    if ! kill -0 "$(<"$pid_file")" >/dev/null 2>&1; then
        cento_die "$label socket tunnel failed. See $log_file"
    fi
    printf '%s socket tunnel started (pid %s): %s -> %s:%s\n' "$label" "$(<"$pid_file")" "$socket_path" "$target_host" "$target_port"
}

run_via_socket() {
    local vm_user=$1 vm_host=$2 socket_path=$3 target_user=$4 host_alias=$5 default_command=$6
    shift 6
    local remote_command
    if [[ $# -gt 0 ]]; then
        remote_command="$*"
    else
        remote_command="$default_command"
    fi
    exec ssh \
        -o BatchMode=yes \
        -o StrictHostKeyChecking=accept-new \
        -o ProxyCommand="ssh ${vm_user}@${vm_host} nc -U ${socket_path}" \
        "${target_user}@${host_alias}" \
        "$remote_command"
}

open_shell_via_socket() {
    local vm_user=$1 vm_host=$2 socket_path=$3 target_user=$4 host_alias=$5
    exec ssh \
        -o StrictHostKeyChecking=accept-new \
        -o ProxyCommand="ssh ${vm_user}@${vm_host} nc -U ${socket_path}" \
        "${target_user}@${host_alias}"
}

mesh_status() {
    local vm_user=$1 vm_host=$2
    ssh -o StrictHostKeyChecking=accept-new "${vm_user}@${vm_host}" 'ls -l /tmp/cento-*.sock 2>/dev/null || true'
}

docs() {
    cat <<'DOCS'
cento bridge creates a reverse SSH tunnel from this machine to the OCI VM.

Default relay:
  VM: opc@129.213.17.199
  VM-side tunnel: 127.0.0.1:2222
  Local target: 127.0.0.1:22

Start the bridge on this machine:
  cento bridge start

Connect from the Mac while the bridge is running:
  cento bridge mac-command

The default tunnel requests a localhost bind on the VM. Some VM sshd
configurations override remote-forward binds to all interfaces; OCI ingress rules
still control whether that VM-side port is reachable from the internet. Your Mac
can use the ProxyJump command either way.

If you intentionally want a public VM port, use --public, then configure OCI
security rules, the VM firewall, and sshd GatewayPorts on the VM.
DOCS
}

main() {
    local command=${1:-status}
    if [[ $# -gt 0 ]]; then
        shift
    fi
    if [[ "$command" == "--from-mac" ]]; then
        command="from-mac"
    fi

    local vm_user=$DEFAULT_VM_USER
    local vm_host=$DEFAULT_VM_HOST
    local identity=$DEFAULT_VM_IDENTITY
    local remote_bind=$DEFAULT_REMOTE_BIND
    local remote_port=$DEFAULT_REMOTE_PORT
    local local_host=$DEFAULT_LOCAL_HOST
    local local_port=$DEFAULT_LOCAL_PORT
    local local_user=$DEFAULT_LOCAL_USER
    local mac_user=$DEFAULT_MAC_USER
    local -a passthrough=()

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --)
                shift
                passthrough=("$@")
                break
                ;;
            --vm-host)
                vm_host=${2:-}
                shift 2
                ;;
            --vm-user)
                vm_user=${2:-}
                shift 2
                ;;
            --identity)
                identity=${2:-}
                shift 2
                ;;
            --remote-port)
                remote_port=${2:-}
                shift 2
                ;;
            --remote-bind)
                remote_bind=${2:-}
                shift 2
                ;;
            --local-host)
                local_host=${2:-}
                shift 2
                ;;
            --local-port)
                local_port=${2:-}
                shift 2
                ;;
            --local-user)
                local_user=${2:-}
                shift 2
                ;;
            --mac-user)
                mac_user=${2:-}
                shift 2
                ;;
            --public)
                remote_bind="0.0.0.0"
                shift
                ;;
            -h|--help)
                usage
                return 0
                ;;
            *)
                if [[ "$command" == "from-mac" ]]; then
                    passthrough=("$@")
                    break
                fi
                cento_die "Unknown option: $1"
                ;;
        esac
    done

    identity=$(expand_path "$identity")

    case "$command" in
        help|-h|--help)
            usage
            ;;
        docs)
            docs
            ;;
        command)
            build_ssh_command foreground "$vm_user" "$vm_host" "$identity" "$remote_bind" "$remote_port" "$local_host" "$local_port"
            ;;
        mac-command)
            print_mac_command "$vm_user" "$vm_host" "$remote_port" "$local_user"
            ;;
        status)
            print_status "$vm_user" "$vm_host" "$remote_bind" "$remote_port" "$local_host" "$local_port" "$local_user"
            ;;
        check)
            cento_require_cmd ssh
            cento_require_cmd git
            run_check "$vm_user" "$vm_host" "$remote_port" "$local_user"
            ;;
        from-mac)
            cento_require_cmd ssh
            run_from_mac "$vm_user" "$vm_host" "$remote_port" "$local_user" "${passthrough[@]}"
            ;;
        expose-linux)
            start_socket_tunnel "$vm_user" "$vm_host" "$DEFAULT_LINUX_SOCKET" "$local_host" "$local_port" "linux"
            ;;
        expose-mac)
            start_mac_sshd
            start_socket_tunnel "$vm_user" "$vm_host" "$DEFAULT_MAC_SOCKET" "127.0.0.1" "$DEFAULT_MAC_SSHD_PORT" "mac"
            ;;
        to-linux)
            cento_require_cmd ssh
            if [[ ${#passthrough[@]} -gt 0 ]]; then
                run_via_socket "$vm_user" "$vm_host" "$DEFAULT_LINUX_SOCKET" "$local_user" "cento-linux" "" "${passthrough[@]}"
            else
                open_shell_via_socket "$vm_user" "$vm_host" "$DEFAULT_LINUX_SOCKET" "$local_user" "cento-linux"
            fi
            ;;
        to-mac)
            cento_require_cmd ssh
            if [[ ${#passthrough[@]} -gt 0 ]]; then
                run_via_socket "$vm_user" "$vm_host" "$DEFAULT_MAC_SOCKET" "$mac_user" "cento-mac" "" "${passthrough[@]}"
            else
                open_shell_via_socket "$vm_user" "$vm_host" "$DEFAULT_MAC_SOCKET" "$mac_user" "cento-mac"
            fi
            ;;
        context-linux)
            cento_require_cmd ssh
            run_via_socket "$vm_user" "$vm_host" "$DEFAULT_LINUX_SOCKET" "$local_user" "cento-linux" 'cd "$HOME/projects/cento" && ./scripts/cento.sh gather-context --no-remote | head -90'
            ;;
        context-mac)
            cento_require_cmd ssh
            run_via_socket "$vm_user" "$vm_host" "$DEFAULT_MAC_SOCKET" "$mac_user" "cento-mac" "$HOME/bin/cento gather-context --no-remote | head -90"
            ;;
        mesh-status)
            cento_require_cmd ssh
            mesh_status "$vm_user" "$vm_host"
            ;;
        start)
            cento_require_cmd ssh
            [[ -f "$identity" ]] || cento_die "Missing OCI private key: $identity"
            cento_ensure_dir "$STATE_DIR"
            if is_running; then
                printf 'Bridge already running (pid %s).\n' "$(<"$PID_FILE")"
                return 0
            fi
            if [[ "$remote_bind" == "0.0.0.0" ]]; then
                cento_warn "Public mode requires VM sshd GatewayPorts plus OCI/firewall ingress for port $remote_port."
            fi
            local -a ssh_command=(
                ssh
                -N
                -T
                -o BatchMode=yes
                -o ExitOnForwardFailure=yes
                -o ServerAliveInterval=30
                -o ServerAliveCountMax=3
                -i "$identity"
                -R "${remote_bind}:${remote_port}:${local_host}:${local_port}"
                "${vm_user}@${vm_host}"
            )
            local pid
            if cento_have_cmd setsid; then
                rm -f "$PID_FILE"
                setsid -f bash -c 'printf "%s\n" "$$" > "$1"; shift; exec "$@"' bridge-launch "$PID_FILE" "${ssh_command[@]}" >"$LOG_FILE" 2>&1 </dev/null
                sleep 0.2
                pid=$(<"$PID_FILE")
            else
                nohup "${ssh_command[@]}" >"$LOG_FILE" 2>&1 </dev/null &
                pid=$!
                printf '%s\n' "$pid" >"$PID_FILE"
            fi
            sleep 1
            if ! kill -0 "$pid" >/dev/null 2>&1; then
                rm -f "$PID_FILE"
                cento_die "Bridge failed to start. See $LOG_FILE"
            fi
            printf 'Bridge started (pid %s).\n' "$pid"
            printf 'Mac command: '
            print_mac_command "$vm_user" "$vm_host" "$remote_port" "$local_user"
            ;;
        foreground)
            cento_require_cmd ssh
            [[ -f "$identity" ]] || cento_die "Missing OCI private key: $identity"
            if [[ "$remote_bind" == "0.0.0.0" ]]; then
                cento_warn "Public mode requires VM sshd GatewayPorts plus OCI/firewall ingress for port $remote_port."
            fi
            exec ssh \
                -N \
                -T \
                -o ExitOnForwardFailure=yes \
                -o ServerAliveInterval=30 \
                -o ServerAliveCountMax=3 \
                -i "$identity" \
                -R "${remote_bind}:${remote_port}:${local_host}:${local_port}" \
                "${vm_user}@${vm_host}"
            ;;
        stop)
            if ! is_running; then
                printf 'Bridge is not running.\n'
                rm -f "$PID_FILE"
                return 0
            fi
            local pid
            pid=$(<"$PID_FILE")
            kill "$pid"
            rm -f "$PID_FILE"
            printf 'Bridge stopped (pid %s).\n' "$pid"
            ;;
        restart)
            "$0" stop
            "$0" start \
                --vm-user "$vm_user" \
                --vm-host "$vm_host" \
                --identity "$identity" \
                --remote-bind "$remote_bind" \
                --remote-port "$remote_port" \
                --local-host "$local_host" \
                --local-port "$local_port" \
                --local-user "$local_user"
            ;;
        *)
            usage
            cento_die "Unknown bridge command: $command"
            ;;
    esac
}

main "$@"
