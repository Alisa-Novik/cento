#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$SCRIPT_DIR/lib/common.sh"

CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/cento"
CONFIG_FILE="$CONFIG_DIR/notify.json"
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/cento"
COUNTER_FILE="$STATE_DIR/notify-counts.json"
EVENTS_FILE="$STATE_DIR/notify-events.jsonl"
DEFAULT_SERVER="https://ntfy.sh"
DEFAULT_TARGET="iphone"

usage() {
    cat <<'USAGE'
Usage: cento notify <command> [args...]

Commands:
  setup [TARGET] TOPIC       Save ntfy topic for a target (default target: iphone)
  status                     Show configured notification targets
  stats                      Show sent notification counters
  TARGET MESSAGE...          Send MESSAGE to TARGET
  send TARGET MESSAGE...     Send MESSAGE to TARGET
  test [TARGET]              Send a test notification

Environment:
  CENTO_NTFY_SERVER          Override ntfy server URL (default: https://ntfy.sh)

Examples:
  cento notify setup iphone cento-private-topic
  cento notify stats
  cento notify iphone "Cluster job finished"
  cento notify all "Linux healed"
  cento notify test iphone
USAGE
}

ensure_config() {
    cento_ensure_dir "$CONFIG_DIR"
    if [[ ! -f "$CONFIG_FILE" ]]; then
        python3 - "$CONFIG_FILE" "$DEFAULT_SERVER" <<'PY'
import json
import sys
from pathlib import Path

path, server = sys.argv[1:]
payload = {"server": server, "targets": {}}
Path(path).write_text(json.dumps(payload, indent=2) + "\n")
PY
        chmod 600 "$CONFIG_FILE"
    fi
}

setup_target() {
    local target topic server
    if [[ $# -eq 1 ]]; then
        target=$DEFAULT_TARGET
        topic=$1
    elif [[ $# -eq 2 ]]; then
        target=$1
        topic=$2
    else
        cento_die "Usage: cento notify setup [TARGET] TOPIC"
    fi
    server=${CENTO_NTFY_SERVER:-$DEFAULT_SERVER}
    ensure_config
    python3 - "$CONFIG_FILE" "$server" "$target" "$topic" <<'PY'
import json
import sys
from pathlib import Path

path, server, target, topic = sys.argv[1:]
config_path = Path(path)
data = json.loads(config_path.read_text())
data["server"] = server.rstrip("/")
data.setdefault("targets", {})[target] = {"topic": topic}
config_path.write_text(json.dumps(data, indent=2) + "\n")
PY
    chmod 600 "$CONFIG_FILE"
    printf 'configured %s notification target in %s\n' "$target" "$CONFIG_FILE"
}

target_topic() {
    local target=$1
    ensure_config
    python3 - "$CONFIG_FILE" "$target" <<'PY'
import json
import sys
from pathlib import Path

path, target = sys.argv[1:]
data = json.loads(Path(path).read_text())
topic = data.get("targets", {}).get(target, {}).get("topic", "")
if topic:
    print(topic)
    raise SystemExit(0)
raise SystemExit(1)
PY
}

server_url() {
    ensure_config
    python3 - "$CONFIG_FILE" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text())
print((data.get("server") or "https://ntfy.sh").rstrip("/"))
PY
}

list_targets() {
    ensure_config
    python3 - "$CONFIG_FILE" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text())
print(f"config {sys.argv[1]}")
print(f"server {data.get('server', 'https://ntfy.sh')}")
targets = data.get("targets", {})
if not targets:
    print("targets none")
else:
    for name in sorted(targets):
        topic = targets[name].get("topic", "")
        masked = topic[:6] + "..." + topic[-4:] if len(topic) > 12 else topic
        print(f"{name:<8} {masked}")
PY
}

record_send() {
    local target=$1 message=$2
    cento_ensure_dir "$STATE_DIR"
    python3 - "$COUNTER_FILE" "$EVENTS_FILE" "$target" "$message" <<'PY'
import hashlib
import json
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path

counter_path, events_path, target, message = sys.argv[1:]
counter_file = Path(counter_path)
events_file = Path(events_path)
now = datetime.now(timezone.utc).isoformat()
if counter_file.exists():
    try:
        data = json.loads(counter_file.read_text())
    except Exception:
        data = {}
else:
    data = {}
data["total"] = int(data.get("total", 0)) + 1
targets = data.setdefault("targets", {})
target_data = targets.setdefault(target, {"count": 0})
target_data["count"] = int(target_data.get("count", 0)) + 1
target_data["last_sent_at"] = now
target_data["last_message_hash"] = hashlib.sha256(message.encode()).hexdigest()[:12]
data["last_sent_at"] = now
data["last_target"] = target
data["host"] = socket.gethostname()
counter_file.write_text(json.dumps(data, indent=2) + "\n")
event = {
    "sent_at": now,
    "target": target,
    "host": socket.gethostname(),
    "message_hash": hashlib.sha256(message.encode()).hexdigest()[:12],
    "message_preview": message[:160],
}
with events_file.open("a") as fh:
    fh.write(json.dumps(event) + "\n")
PY
}

show_stats() {
    cento_ensure_dir "$STATE_DIR"
    python3 - "$COUNTER_FILE" "$EVENTS_FILE" <<'PY'
import json
import sys
from pathlib import Path

counter_file, events_file = map(Path, sys.argv[1:])
if not counter_file.exists():
    print("total 0")
    print(f"counter {counter_file}")
    raise SystemExit(0)
data = json.loads(counter_file.read_text())
print(f"total {data.get('total', 0)}")
print(f"host {data.get('host', 'unknown')}")
print(f"last_sent_at {data.get('last_sent_at', 'never')}")
for target, item in sorted(data.get("targets", {}).items()):
    print(f"{target:<8} {item.get('count', 0)} last={item.get('last_sent_at', 'never')} hash={item.get('last_message_hash', '')}")
print(f"counter {counter_file}")
if events_file.exists():
    print(f"events {events_file}")
PY
}

send_one() {
    local target=$1
    shift
    [[ $# -gt 0 ]] || cento_die "Usage: cento notify TARGET MESSAGE..."
    local message=$*
    local topic server title
    topic=$(target_topic "$target") || cento_die "No ntfy topic configured for target '$target'. Run: cento notify setup $target TOPIC"
    server=$(server_url)
    title="Cento ${target}"
    cento_require_cmd curl
    curl \
        --fail \
        --silent \
        --show-error \
        -H "Title: $title" \
        -H "Tags: computer" \
        -d "$message" \
        "$server/$topic" >/dev/null
    record_send "$target" "$message"
    printf 'sent %s notification\n' "$target"
}

send_all() {
    shift || true
    [[ $# -gt 0 ]] || cento_die "Usage: cento notify all MESSAGE..."
    ensure_config
    local -a targets=()
    mapfile -t targets < <(python3 - "$CONFIG_FILE" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text())
for name in sorted(data.get("targets", {})):
    print(name)
PY
)
    [[ ${#targets[@]} -gt 0 ]] || cento_die "No notification targets configured. Run: cento notify setup iphone TOPIC"
    local target
    for target in "${targets[@]}"; do
        send_one "$target" "$@"
    done
}

main() {
    local command=${1:-help}
    [[ $# -eq 0 ]] || shift
    case "$command" in
        help|-h|--help)
            usage
            ;;
        setup)
            setup_target "$@"
            ;;
        status)
            list_targets
            ;;
        stats)
            show_stats
            ;;
        send)
            [[ $# -ge 2 ]] || cento_die "Usage: cento notify send TARGET MESSAGE..."
            local target=$1
            shift
            send_one "$target" "$@"
            ;;
        test)
            target=${1:-$DEFAULT_TARGET}
            send_one "$target" "Cento test notification from $(hostname 2>/dev/null || printf unknown)"
            ;;
        all)
            send_all "$command" "$@"
            ;;
        *)
            send_one "$command" "$@"
            ;;
    esac
}

main "$@"
