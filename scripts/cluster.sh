#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$SCRIPT_DIR/lib/common.sh"

ROOT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/cento"
NODE_FILE="$CONFIG_DIR/node.json"
CLUSTER_FILE="$CONFIG_DIR/cluster.json"
DEFAULT_VM_USER="opc"
DEFAULT_VM_HOST="129.213.17.199"
DEFAULT_LINUX_SOCKET="/tmp/cento-linux.sock"
DEFAULT_MAC_SOCKET="/tmp/cento-mac.sock"
HEARTBEAT_DIR="$CONFIG_DIR/heartbeats"
RELAY_HEARTBEAT_DIR=".cento/heartbeats"
COMPANION_HEARTBEAT_TTL_SECONDS=300
CLUSTER_REQUEST_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/cento/cluster-requests"

if [[ -t 1 ]] && command -v tput >/dev/null 2>&1; then
    C_RESET=$(tput sgr0)
    C_BOLD=$(tput bold)
    C_DIM=$(tput dim)
    C_GREEN=$(tput setaf 2)
    C_YELLOW=$(tput setaf 3)
    C_RED=$(tput setaf 1)
    C_BLUE=$(tput setaf 6)
else
    C_RESET=""
    C_BOLD=""
    C_DIM=""
    C_GREEN=""
    C_YELLOW=""
    C_RED=""
    C_BLUE=""
fi

usage() {
    cat <<'USAGE'
Usage: cento cluster <command> [args...]

Commands:
  init                 Write managed node.json and cluster.json defaults
  nodes                List known cluster nodes
  status               Show mesh, service, and node reachability
  exec NODE -- CMD     Run a command on a node
  sync                 Show git drift only; does not modify either node
  heal [NODE|all]      Start or repair bridge services
  heartbeat [NODE]     Show companion heartbeat state
  metric memory        Print cluster memory consumption
  ask TEXT...          Execute a small natural-language cluster request

Examples:
  cento cluster init
  cento cluster status
  cento cluster exec linux -- tmux ls
  cento cluster sync
  cento cluster heal
  cento cluster heartbeat iphone
  cento cluster ask "send me notification with total memory consumption on the cluster"

Use `cento cluster help COMMAND` for command-specific help.
USAGE
}

help_command() {
    case "${1:-}" in
        init)
            cat <<'USAGE'
Usage: cento cluster init

Writes:
  ~/.config/cento/node.json
  ~/.config/cento/cluster.json
USAGE
            ;;
        nodes)
            cat <<'USAGE'
Usage: cento cluster nodes

Lists known nodes from cluster.json.
USAGE
            ;;
        status)
            cat <<'USAGE'
Usage: cento cluster status

Shows relay socket visibility, node reachability, and local bridge service state.
USAGE
            ;;
        exec)
            cat <<'USAGE'
Usage: cento cluster exec NODE -- CMD [ARGS...]

Runs a command on NODE. Local node commands run directly; remote node commands
run through the OCI Unix-socket mesh.
USAGE
            ;;
        sync)
            cat <<'USAGE'
Usage: cento cluster sync

Shows git branch, dirty state, and HEAD for each reachable node. Read-only.
USAGE
            ;;
        heal)
            cat <<'USAGE'
Usage: cento cluster heal [NODE|all]

Starts or repairs bridge services. Defaults to all reachable nodes.
USAGE
            ;;
        heartbeat)
            cat <<'USAGE'
Usage: cento cluster heartbeat [NODE]

Shows companion heartbeat state. Workstation nodes answer locally; Linux queries
the Mac control-plane heartbeat for companion devices such as iphone.
USAGE
            ;;
        metric)
            cat <<'USAGE'
Usage: cento cluster metric memory

Prints cluster memory consumption across workstation nodes. This is intended for
agents and scripts that need metric data without invoking cluster ask.
USAGE
            ;;
        ask)
            cat <<'USAGE'
Usage: cento cluster ask TEXT...

Submits TEXT to `codex exec` as an asynchronous cluster command. Codex can run
Cento commands on the cluster, choose a response template, and notify the phone.
USAGE
            ;;
        *)
            usage
            ;;
    esac
}

color() {
    local color_value=$1
    shift
    printf '%s%s%s' "$color_value" "$*" "$C_RESET"
}

ok() {
    color "$C_GREEN" "$*"
}

warn() {
    color "$C_YELLOW" "$*"
}

bad() {
    color "$C_RED" "$*"
}

info() {
    color "$C_BLUE" "$*"
}

quote_remote_command() {
    printf '%q ' "$@"
}

remote_shell_command() {
    if [[ $# -eq 1 ]]; then
        printf '%s\n' "$1"
        return
    fi
    printf '%q ' "$@"
    printf '\n'
}

socket_proxy_command() {
    local vm_user=$1 vm_host=$2 socket=$3
    printf 'ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 -o ConnectionAttempts=1 -o ServerAliveInterval=5 -o ServerAliveCountMax=1 %s@%s timeout 6 nc -U %q' "$vm_user" "$vm_host" "$socket"
}

heading() {
    printf '%s%s%s\n' "$C_BOLD" "$*" "$C_RESET"
}

platform_id() {
    case "$(uname -s)" in
        Darwin) printf 'macos\n' ;;
        Linux) printf 'linux\n' ;;
        *) uname -s | tr '[:upper:]' '[:lower:]' ;;
    esac
}

node_socket_for() {
    case "$1" in
        macos) printf '%s\n' "$DEFAULT_MAC_SOCKET" ;;
        linux) printf '%s\n' "$DEFAULT_LINUX_SOCKET" ;;
        *) printf '\n' ;;
    esac
}

node_repo_for() {
    case "$1" in
        macos) printf '/Users/anovik-air/cento\n' ;;
        linux) printf '/home/alice/projects/cento\n' ;;
        *) printf '%s\n' "$ROOT_DIR" ;;
    esac
}

node_user_for() {
    case "$1" in
        macos) printf 'anovik-air\n' ;;
        linux) printf 'alice\n' ;;
        *) printf '%s\n' "${USER:-unknown}" ;;
    esac
}

write_node_config() {
    local id host user socket service
    id=$(platform_id)
    host=$(hostname 2>/dev/null || printf unknown)
    user=${USER:-unknown}
    socket=$(node_socket_for "$id")
    case "$id" in
        macos) service="launchd:com.cento.bridge-mac" ;;
        linux) service="systemd:user:cento-bridge-linux.service" ;;
        *) service="manual" ;;
    esac
    cento_ensure_dir "$CONFIG_DIR"
    python3 - "$NODE_FILE" "$id" "$host" "$user" "$HOME" "$ROOT_DIR" "$socket" "$service" <<'PY'
import json
import sys
from pathlib import Path

path, node_id, host, user, home, repo, socket, service = sys.argv[1:]
payload = {
    "id": node_id,
    "hostname": host,
    "platform": node_id,
    "user": user,
    "home": home,
    "repo": repo,
    "socket": socket,
    "role": "workstation",
    "bridge_service": service,
    "capabilities": ["shell", "tmux", "git", "cento"],
}
Path(path).write_text(json.dumps(payload, indent=2) + "\n")
PY
}

write_cluster_config() {
    cento_ensure_dir "$CONFIG_DIR"
    python3 - "$CLUSTER_FILE" "$DEFAULT_VM_USER" "$DEFAULT_VM_HOST" <<'PY'
import json
import sys
from pathlib import Path

path, vm_user, vm_host = sys.argv[1:]
payload = {
    "version": 1,
    "relay": {"user": vm_user, "host": vm_host},
    "nodes": [
        {
            "id": "linux",
            "platform": "linux",
            "user": "alice",
            "host_alias": "cento-linux",
            "repo": "/home/alice/projects/cento",
            "socket": "/tmp/cento-linux.sock",
            "bridge_service": "systemd:user:cento-bridge-linux.service",
            "capabilities": ["shell", "tmux", "git", "cento"],
        },
        {
            "id": "macos",
            "platform": "macos",
            "user": "anovik-air",
            "host_alias": "cento-mac",
            "repo": "/Users/anovik-air/cento",
            "socket": "/tmp/cento-mac.sock",
            "bridge_service": "launchd:com.cento.bridge-mac",
            "capabilities": ["shell", "tmux", "git", "cento"],
        },
    ],
}
Path(path).write_text(json.dumps(payload, indent=2) + "\n")
PY
}

ensure_cluster_config() {
    [[ -f "$NODE_FILE" ]] || write_node_config
    [[ -f "$CLUSTER_FILE" ]] || write_cluster_config
}

record_companion_heartbeat() {
    local node_id=${CENTO_COMPANION_NODE:-}
    [[ -n "$node_id" ]] || return 0
    ensure_cluster_config
    cento_ensure_dir "$HEARTBEAT_DIR"
    local heartbeat_file="$HEARTBEAT_DIR/$node_id.json"
    python3 - "$heartbeat_file" "$node_id" <<'PY'
import json
import os
import socket
import sys
import time
from pathlib import Path

path, node_id = sys.argv[1:]
payload = {
    "id": node_id,
    "last_seen": int(time.time()),
    "via": os.environ.get("SSH_CONNECTION", "unknown"),
    "host": socket.gethostname(),
}
Path(path).write_text(json.dumps(payload, indent=2) + "\n")
PY
    publish_companion_heartbeat "$node_id" "$heartbeat_file" || true
}

publish_companion_heartbeat() {
    local node_id=$1 heartbeat_file=$2 vm_user vm_host
    vm_user=$(relay_field user)
    vm_host=$(relay_field host)
    ssh \
        -o BatchMode=yes \
        -o StrictHostKeyChecking=accept-new \
        -o ConnectTimeout=5 \
        "${vm_user}@${vm_host}" \
        "mkdir -p '$RELAY_HEARTBEAT_DIR' && cat > '$RELAY_HEARTBEAT_DIR/$node_id.json'" < "$heartbeat_file" >/dev/null 2>&1
}

companion_recent() {
    local node_id=$1
    companion_heartbeat_state "$node_id" >/dev/null
}

heartbeat_json_state() {
    local ttl=$1
    python3 -c 'import json, sys, time
ttl = int(sys.argv[1])
try:
    data = json.loads(sys.stdin.read())
    last_seen = int(data.get("last_seen", 0))
except Exception:
    print("invalid")
    raise SystemExit(1)
age = int(time.time() - last_seen)
state = "connected" if age <= ttl else "stale"
print("{} age={}s host={} via={}".format(state, age, data.get("host", "unknown"), data.get("via", "unknown")))
raise SystemExit(0 if state == "connected" else 1)' "$ttl"
}

companion_heartbeat_state() {
    local node_id=$1
    local local_file="$HEARTBEAT_DIR/$node_id.json"
    if [[ -f "$local_file" ]] && heartbeat_json_state "$COMPANION_HEARTBEAT_TTL_SECONDS" < "$local_file"; then
        return 0
    fi

    local vm_user vm_host
    vm_user=$(relay_field user)
    vm_host=$(relay_field host)
    ssh \
        -o BatchMode=yes \
        -o StrictHostKeyChecking=accept-new \
        -o ConnectTimeout=5 \
        "${vm_user}@${vm_host}" \
        "cat '$RELAY_HEARTBEAT_DIR/$node_id.json'" 2>/dev/null | heartbeat_json_state "$COMPANION_HEARTBEAT_TTL_SECONDS"
}

cluster_heartbeat() {
    local target=${1:-}
    ensure_cluster_config
    if [[ -n "$target" ]]; then
        printf '%-8s ' "$target"
        companion_heartbeat_state "$target"
        return
    fi

    heading "heartbeats"
    while IFS= read -r node_id; do
        [[ "$(node_field "$node_id" role)" == "companion" ]] || continue
        printf '%-8s ' "$node_id"
        companion_heartbeat_state "$node_id" || true
    done < <(python3 - "$CLUSTER_FILE" <<'PY'
import json
import sys
from pathlib import Path
for node in json.loads(Path(sys.argv[1]).read_text()).get("nodes", []):
    print(node["id"])
PY
)
}

cluster_init() {
    write_node_config
    write_cluster_config
    printf '%s %s\n' "$(ok wrote)" "$NODE_FILE"
    printf '%s %s\n' "$(ok wrote)" "$CLUSTER_FILE"
}

local_node_id() {
    platform_id
}

node_field() {
    local node_id=$1 field=$2
    ensure_cluster_config
    python3 - "$CLUSTER_FILE" "$node_id" "$field" <<'PY'
import json
import sys
from pathlib import Path

path, node_id, field = sys.argv[1:]
data = json.loads(Path(path).read_text())
for node in data.get("nodes", []):
    if node.get("id") == node_id:
        print(node.get(field, ""))
        raise SystemExit(0)
raise SystemExit(1)
PY
}

relay_field() {
    local field=$1
    ensure_cluster_config
    python3 - "$CLUSTER_FILE" "$field" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text())
print(data.get("relay", {}).get(sys.argv[2], ""))
PY
}

list_nodes() {
    ensure_cluster_config
    heading "nodes"
    python3 - "$CLUSTER_FILE" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text())
for node in data.get("nodes", []):
    print(f"{node['id']:<8} {node['platform']:<7} {node['user']:<12} {node['socket']:<24} {node['repo']}")
PY
}

run_remote_node() {
    local node_id=$1
    shift
    local socket user host_alias vm_user vm_host remote_command remote_invocation proxy_command
    socket=$(node_field "$node_id" socket)
    user=$(node_field "$node_id" user)
    host_alias=$(node_field "$node_id" host_alias)
    vm_user=$(relay_field user)
    vm_host=$(relay_field host)
    remote_command=$(remote_shell_command "$@")
    remote_invocation=$(printf 'bash -lc %q' "$remote_command")
    proxy_command=$(socket_proxy_command "$vm_user" "$vm_host" "$socket")
    local socket_rc
    set +e
    ssh \
        -n \
        -o BatchMode=yes \
        -o StrictHostKeyChecking=accept-new \
        -o ConnectTimeout=8 \
        -o ConnectionAttempts=1 \
        -o ServerAliveInterval=5 \
        -o ServerAliveCountMax=1 \
        -o "ProxyCommand=$proxy_command" \
        "${user}@${host_alias}" \
        "$remote_invocation"
    socket_rc=$?
    set -e
    if [[ $socket_rc -eq 0 ]]; then
        return 0
    fi

    if [[ "$node_id" == "linux" ]]; then
        run_direct_node "$node_id" '/home/alice/projects/cento/scripts/cento.sh bridge expose-linux >/dev/null 2>&1 || true' >/dev/null 2>&1 || true
        set +e
        ssh \
            -n \
            -o BatchMode=yes \
            -o StrictHostKeyChecking=accept-new \
            -o ConnectTimeout=8 \
            -o ConnectionAttempts=1 \
            -o ServerAliveInterval=5 \
            -o ServerAliveCountMax=1 \
            -o "ProxyCommand=$proxy_command" \
            "${user}@${host_alias}" \
            "$remote_invocation"
        socket_rc=$?
        set -e
        if [[ $socket_rc -eq 0 ]]; then
            return 0
        fi
    fi

    run_direct_node "$node_id" "$@" && return 0
    return "$socket_rc"
}

run_direct_node() {
    local node_id=$1
    shift
    local direct_host=""
    case "$node_id" in
        linux)
            direct_host=${CENTO_LINUX_DIRECT_HOST:-alisapad.local}
            ;;
        *)
            return 127
            ;;
    esac

    local user remote_command remote_invocation known_hosts_dir known_hosts_file
    user=$(node_field "$node_id" user)
    remote_command=$(remote_shell_command "$@")
    remote_invocation=$(printf 'bash -lc %q' "$remote_command")
    known_hosts_dir="${XDG_STATE_HOME:-$HOME/.local/state}/cento"
    known_hosts_file="$known_hosts_dir/cluster-known-hosts"
    cento_ensure_dir "$known_hosts_dir"
    ssh \
        -n \
        -o BatchMode=yes \
        -o StrictHostKeyChecking=accept-new \
        -o UserKnownHostsFile="$known_hosts_file" \
        -o ConnectTimeout=5 \
        -o ConnectionAttempts=1 \
        -o ServerAliveInterval=5 \
        -o ServerAliveCountMax=1 \
        "${user}@${direct_host}" \
        "$remote_invocation"
}

cluster_exec() {
    local node_id=${1:-}
    [[ -n "$node_id" ]] || cento_die "Usage: cento cluster exec NODE -- CMD"
    shift
    [[ ${1:-} == "--" ]] || cento_die "Usage: cento cluster exec NODE -- CMD"
    shift
    [[ $# -gt 0 ]] || cento_die "Usage: cento cluster exec NODE -- CMD"

    printf '%s %s %s\n' "$(info exec)" "$node_id" "$*" >&2
    if [[ "$node_id" == "$(local_node_id)" ]]; then
        exec "$@"
    fi
    run_remote_node "$node_id" "$@"
}

node_reachable() {
    local node_id=$1
    if [[ "$node_id" == "$(local_node_id)" ]]; then
        return 0
    fi
    if [[ "$(node_field "$node_id" role)" == "companion" ]]; then
        companion_recent "$node_id"
        return
    fi
    if [[ -n "${CENTO_COMPANION_NODE:-}" ]] && relay_socket_visible "$(node_field "$node_id" socket)"; then
        return 0
    fi
    run_remote_node "$node_id" true >/dev/null 2>&1
}

mesh_summary() {
    if "$BASH" "$SCRIPT_DIR/cento.sh" bridge mesh-status >/dev/null 2>&1; then
        "$BASH" "$SCRIPT_DIR/cento.sh" bridge mesh-status
    else
        printf 'mesh unavailable\n'
        return 1
    fi
}

relay_socket_visible() {
    local socket=$1
    [[ -n "$socket" ]] || return 1
    "$BASH" "$SCRIPT_DIR/cento.sh" bridge mesh-status </dev/null 2>/dev/null | grep -Fq -- "$socket"
}

cluster_status() {
    ensure_cluster_config
    heading "cluster status"
    printf 'local       %s\n' "$(ok "$(local_node_id)")"
    printf 'node config %s\n' "$NODE_FILE"
    printf 'registry    %s\n' "$CLUSTER_FILE"
    printf '\n'
    heading "mesh"
    mesh_summary || true
    printf '\n'
    heading "nodes"
    while IFS= read -r node_id; do
        if node_reachable "$node_id"; then
            printf '%-8s %s\n' "$node_id" "$(ok connected)"
        else
            printf '%-8s %s\n' "$node_id" "$(bad disconnected)"
        fi
    done < <(python3 - "$CLUSTER_FILE" <<'PY'
import json
import sys
from pathlib import Path
for node in json.loads(Path(sys.argv[1]).read_text()).get("nodes", []):
    print(node["id"])
PY
)
}

cluster_sync() {
    ensure_cluster_config
    heading "git drift"
    while IFS= read -r node_id; do
        local repo
        repo=$(node_field "$node_id" repo)
        printf '\n%s\n' "$(info "[$node_id]")"
        if [[ "$node_id" == "$(local_node_id)" ]]; then
            git -C "$repo" status --short --branch || true
            git -C "$repo" rev-parse --short HEAD || true
        elif node_reachable "$node_id"; then
            run_remote_node "$node_id" "git -C '$repo' status --short --branch; git -C '$repo' rev-parse --short HEAD" || true
        else
            bad unreachable
            printf '\n'
        fi
    done < <(python3 - "$CLUSTER_FILE" <<'PY'
import json
import sys
from pathlib import Path
for node in json.loads(Path(sys.argv[1]).read_text()).get("nodes", []):
    print(node["id"])
PY
)
}

service_status() {
    case "$(local_node_id)" in
        linux)
            systemctl --user is-active cento-bridge-linux.service 2>/dev/null || true
            ;;
        macos)
            launchctl print "gui/$(id -u)/com.cento.bridge-mac" >/dev/null 2>&1 && printf 'com.cento.bridge-mac active\n' || printf 'com.cento.bridge-mac inactive\n'
            ;;
    esac
}

repair_local() {
    case "$(local_node_id)" in
        linux)
            "$BASH" "$SCRIPT_DIR/cento.sh" bridge install-linux-service || true
            "$BASH" "$SCRIPT_DIR/cento.sh" bridge expose-linux
            ;;
        macos)
            "$BASH" "$SCRIPT_DIR/cento.sh" bridge install-mac-service || true
            "$BASH" "$SCRIPT_DIR/cento.sh" bridge expose-mac
            ;;
        *)
            cento_die "No repair strategy for local platform: $(local_node_id)"
            ;;
    esac
}

repair_remote() {
    local node_id=$1
    case "$node_id" in
        linux)
            run_remote_node linux '/home/alice/projects/cento/scripts/cento.sh bridge install-linux-service || true; /home/alice/projects/cento/scripts/cento.sh bridge expose-linux'
            ;;
        macos)
            run_remote_node macos '/opt/homebrew/bin/bash /Users/anovik-air/cento/scripts/cento.sh bridge install-mac-service || true; /opt/homebrew/bin/bash /Users/anovik-air/cento/scripts/cento.sh bridge expose-mac'
            ;;
        *)
            cento_die "No repair strategy for node: $node_id"
            ;;
    esac
}

cluster_heal() {
    local target=${1:-all}
    ensure_cluster_config
    heading "heal"
    if [[ "$target" == "all" ]]; then
        printf '%-8s %s\n' "$(local_node_id)" "$(info local)"
        repair_local || true
        while IFS= read -r node_id; do
            [[ "$node_id" != "$(local_node_id)" ]] || continue
            if node_reachable "$node_id"; then
                printf '%-8s %s\n' "$node_id" "$(info remote)"
                repair_remote "$node_id" || true
            else
                printf '%-8s %s\n' "$node_id" "$(warn 'unreachable; skipped')"
            fi
        done < <(python3 - "$CLUSTER_FILE" <<'PY'
import json
import sys
from pathlib import Path
for node in json.loads(Path(sys.argv[1]).read_text()).get("nodes", []):
    print(node["id"])
PY
)
        return 0
    fi
    if [[ "$target" == "$(local_node_id)" ]]; then
        repair_local
    else
        repair_remote "$target"
    fi
}

memory_line_command() {
    cat <<'EOF'
python3 - <<'PY'
import platform

node = platform.node()
system = platform.system()
used_mb = 0
total_mb = 0

if system == "Darwin":
    import subprocess
    pagesize = int(subprocess.check_output(["pagesize"], text=True).strip())
    stats = subprocess.check_output(["vm_stat"], text=True)
    values = {}
    for line in stats.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        token = value.strip().rstrip(".").split()[0]
        if token.isdigit():
            values[key.strip()] = int(token)
    used_pages = (
        values.get("Pages active", 0)
        + values.get("Pages wired down", 0)
        + values.get("Pages occupied by compressor", 0)
    )
    used_mb = used_pages * pagesize // 1024 // 1024
    try:
        memsize = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip())
        total_mb = memsize // 1024 // 1024
    except Exception:
        total_mb = 0
else:
    data = {}
    with open("/proc/meminfo") as fh:
        for line in fh:
            key, value = line.split(":", 1)
            data[key] = int(value.strip().split()[0])
    total_kb = data.get("MemTotal", 0)
    available_kb = data.get("MemAvailable", 0)
    used_mb = (total_kb - available_kb) // 1024
    total_mb = total_kb // 1024

print(f"{node} used_mb={used_mb} total_mb={total_mb}")
PY
EOF
}

cluster_memory_report() {
    ensure_cluster_config
    local command output node used total
    command=$(memory_line_command)
    output=""
    while IFS= read -r node_id; do
        [[ "$(node_field "$node_id" role)" == "companion" ]] && continue
        if [[ "$node_id" == "$(local_node_id)" ]]; then
            output+="$("$BASH" -lc "$command")"$'\n'
        elif node_reachable "$node_id"; then
            output+="$(run_remote_node "$node_id" bash -lc "$command")"$'\n'
        else
            output+="$node_id unreachable"$'\n'
        fi
    done < <(python3 - "$CLUSTER_FILE" <<'PY'
import json
import sys
from pathlib import Path
for node in json.loads(Path(sys.argv[1]).read_text()).get("nodes", []):
    print(node["id"])
PY
)
    printf '%s' "$output" | python3 -c 'import re
import sys

rows = []
total_used = 0
total_mem = 0
for line in sys.stdin.read().splitlines():
    match = re.search(r"^(.*?) used_mb=(\d+) total_mb=(\d+)", line)
    if not match:
        rows.append(line)
        continue
    name, used, total = match.group(1), int(match.group(2)), int(match.group(3))
    total_used += used
    total_mem += total
    rows.append(f"{name}: {used / 1024:.1f}GB used / {total / 1024:.1f}GB")
summary = f"Cluster memory: {total_used / 1024:.1f}GB used"
if total_mem:
    summary += f" / {total_mem / 1024:.1f}GB total"
print(summary)
for row in rows:
    print(row)
'
}

cluster_ask_prompt() {
    local request=$1 request_id=$2
    local lowered direct_message
    lowered=$(printf '%s' "$request" | tr '[:upper:]' '[:lower:]')
    case "$lowered" in
        "send me "*|"notify me "*)
            direct_message=$request
            direct_message=${direct_message#send me }
            direct_message=${direct_message#notify me }
            cat <<EOF
Run this command from $ROOT_DIR:

/opt/homebrew/bin/bash ./scripts/cento.sh notify iphone "$(printf '%s' "$direct_message" | sed 's/"/\\"/g')"

Then final-answer exactly:
sent notification
EOF
            return
            ;;
    esac
    cat <<EOF
You are the Cento cluster command executor.

Request id: $request_id
Request from iPhone: $request

Operating model:
- This is a command submission, not a chat. Do not ask follow-up questions.
- Execute the needed commands using the Cento repo at $ROOT_DIR.
- You may use Cento cluster/status/exec/notify commands and ordinary shell tools.
- On macOS, run Cento as: /opt/homebrew/bin/bash ./scripts/cento.sh ...
- Do not call ./scripts/cento.sh cluster ask recursively.
- Do not inspect skill files, README files, docs, or long context files.
- Do not run gather-context unless the user explicitly asks for a context report.
- Start by classifying the request and executing the necessary command(s).
- Prefer safe read-only commands unless the request explicitly asks for a repair/action.
- When responding to the human, choose a template style:
  - short: one compact notification
  - list: bullets/lines for multiple items
  - simple_metric_request.html: metric summary; source template is templates/cluster/simple_metric_request.html
- Send the human-facing result with:
  /opt/homebrew/bin/bash ./scripts/cento.sh notify iphone "MESSAGE"
- If the request asks for a notification, notification delivery is the primary output.
- If notification sending fails, include the failure in your final message.
- Keep final stdout to one short status line after work is done.

Useful examples:
- If the request is "send me X" or "notify me X", send X as a short notification.
- For memory metrics, run: /opt/homebrew/bin/bash ./scripts/cento.sh cluster metric memory. Choose simple_metric_request.html style, then notify.
- Never run ./scripts/cento.sh cluster ask from inside this task.
- For health/status requests, use cluster status and notify a concise status.
- For repair/heal requests, run cluster heal, then notify the outcome.
EOF
}

cluster_ask() {
    [[ $# -gt 0 ]] || cento_die "Usage: cento cluster ask TEXT..."
    local request request_id request_dir prompt_file log_file final_file runner_file codex_bin tmux_bin label tmux_session
    request="$*"
    codex_bin=$(command -v codex 2>/dev/null || true)
    if [[ -z "$codex_bin" && -x /opt/homebrew/bin/codex ]]; then
        codex_bin=/opt/homebrew/bin/codex
    fi
    if [[ -z "$codex_bin" && -x /usr/local/bin/codex ]]; then
        codex_bin=/usr/local/bin/codex
    fi
    [[ -n "$codex_bin" ]] || cento_die "codex CLI not found on this node"
    tmux_bin=$(command -v tmux 2>/dev/null || true)
    if [[ -z "$tmux_bin" && -x /opt/homebrew/bin/tmux ]]; then
        tmux_bin=/opt/homebrew/bin/tmux
    fi
    if [[ -z "$tmux_bin" && -x /usr/local/bin/tmux ]]; then
        tmux_bin=/usr/local/bin/tmux
    fi
    request_id="$(date '+%Y%m%d-%H%M%S')-$(printf '%s' "$request" | shasum | awk '{print substr($1,1,8)}')"
    request_dir="$CLUSTER_REQUEST_DIR/$request_id"
    prompt_file="$request_dir/prompt.md"
    log_file="$request_dir/codex.log"
    final_file="$request_dir/final.txt"
    runner_file="$request_dir/run.sh"
    cento_ensure_dir "$request_dir"
    printf '%s\n' "$request" > "$request_dir/request.txt"
    cluster_ask_prompt "$request" "$request_id" > "$prompt_file"
    cat > "$runner_file" <<EOF
#!/usr/bin/env bash
set -euo pipefail
cd "$(printf '%q' "$ROOT_DIR")"
export CENTO_CLUSTER_ASK_ACTIVE=1
launchd_label_file="$(printf '%q' "$request_dir")/launchd_label"
cleanup_launchd_label() {
  if [[ -f "\$launchd_label_file" ]] && command -v launchctl >/dev/null 2>&1; then
    launchctl remove "\$(cat "\$launchd_label_file")" >/dev/null 2>&1 || true
  fi
}
trap cleanup_launchd_label EXIT
prompt=\$(cat "$(printf '%q' "$prompt_file")")
set +e
"$(printf '%q' "$codex_bin")" exec \\
  --dangerously-bypass-approvals-and-sandbox \\
  --ignore-user-config \\
  --ignore-rules \\
  -C "$(printf '%q' "$ROOT_DIR")" \\
  --output-last-message "$(printf '%q' "$final_file")" \\
  "\$prompt" > "$(printf '%q' "$log_file")" 2>&1
rc=\$?
printf '%s\n' "\$rc" > "$(printf '%q' "$request_dir")/exit_code"
exit "\$rc"
EOF
    chmod +x "$runner_file"
    if [[ "$(uname -s)" == "Darwin" ]] && command -v launchctl >/dev/null 2>&1; then
        label="com.cento.cluster-request.$(printf '%s' "$request_id" | tr -c '[:alnum:].-' '-')"
        if launchctl submit -l "$label" -- "$runner_file" >"$request_dir/submit.log" 2>&1; then
            printf '%s\n' "$label" > "$request_dir/launchd_label"
        else
            cat "$request_dir/submit.log" >&2 || true
            if [[ -n "$tmux_bin" ]]; then
                tmux_session="cento-request-$(printf '%s' "$request_id" | tr -c '[:alnum:]-' '-')"
                "$tmux_bin" new-session -d -s "$tmux_session" "$runner_file" >"$request_dir/tmux.log" 2>&1
                printf '%s\n' "$tmux_session" > "$request_dir/tmux_session"
            else
                nohup "$runner_file" >"$request_dir/nohup.log" 2>&1 &
                printf '%s\n' "$!" > "$request_dir/pid"
            fi
        fi
    else
        if [[ -n "$tmux_bin" ]]; then
            tmux_session="cento-request-$(printf '%s' "$request_id" | tr -c '[:alnum:]-' '-')"
            "$tmux_bin" new-session -d -s "$tmux_session" "$runner_file" >"$request_dir/tmux.log" 2>&1
            printf '%s\n' "$tmux_session" > "$request_dir/tmux_session"
        else
            nohup "$runner_file" >/dev/null 2>&1 &
            printf '%s\n' "$!" > "$request_dir/pid"
        fi
    fi
    printf 'submitted cluster request %s\n' "$request_id"
    printf 'log %s\n' "$log_file"
}

main() {
    [[ -n "${CENTO_SKIP_HEARTBEAT:-}" ]] || record_companion_heartbeat
    local command=${1:-status}
    [[ $# -eq 0 ]] || shift
    if [[ "$command" == "ask" && -n "${CENTO_CLUSTER_ASK_ACTIVE:-}" ]]; then
        cento_die "Refusing recursive cluster ask from active Codex request"
    fi
    case "$command" in
        help|-h|--help)
            help_command "${1:-}"
            ;;
        init)
            cluster_init
            ;;
        nodes)
            list_nodes
            ;;
        status)
            cluster_status
            ;;
        exec)
            cluster_exec "$@"
            ;;
        sync)
            cluster_sync
            ;;
        heal)
            cluster_heal "$@"
            ;;
        heartbeat)
            cluster_heartbeat "$@"
            ;;
        metric)
            case "${1:-}" in
                memory)
                    cluster_memory_report
                    ;;
                *)
                    cento_die "Usage: cento cluster metric memory"
                    ;;
            esac
            ;;
        ask)
            cluster_ask "$@"
            ;;
        *)
            usage
            cento_die "Unknown cluster command: $command"
            ;;
    esac
}

main "$@"
