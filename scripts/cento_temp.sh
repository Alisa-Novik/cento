#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
STORE_DIR="${CENTO_TEMP_COMMAND_DIR:-$ROOT_DIR/workspace/runs/temp/commands}"
DEFAULT_COMMAND_ID="${CENTO_TEMP_DEFAULT_COMMAND_ID:-cento-dev-scale-pro-prompt}"

usage() {
  cat <<'USAGE'
Usage:
  cento temp run
  cento temp run [ID] [--dry-run] [--no-copy]
  cento temp show [ID]
  cento temp list
  cento temp add ID --title TITLE --node local|macos|linux --command '...'
  cento temp add ID --title TITLE --node local|macos|linux --command-file PATH
  cento temp add ID --title TITLE --node local|macos|linux --copy-file PATH
  cento temp remove ID
  cento temp path

Cento temp run is the stable ChatGPT Pro bridge. The core operator workflow is
always exactly:

  cento temp run

That command copies the active GPT Pro prompt Markdown into the clipboard and
prints a short copied report. Agents should update the active prompt file and
run this command automatically when asked to create a similar GPT Pro prompt.

Advanced temp commands are short-lived operator wrappers for fragile commands
that should not be pasted as multiline shell, or clipboard shortcuts for local
files. They are stored as JSON under workspace/runs/temp/commands and can target
this node or another cluster node.

Examples:
  cento temp run
  cento temp show
  cento temp add watch-diag --title "Watch diagnostics" --node macos --command-file /tmp/watch-diag.sh
  cento temp run watch-diag
  cento temp run watch-diag --dry-run
  cento temp run watch-diag --no-copy
  cento temp remove watch-diag
USAGE
}

platform() {
  case "$(uname -s)" in
    Darwin) printf 'macos\n' ;;
    Linux) printf 'linux\n' ;;
    *) uname -s | tr '[:upper:]' '[:lower:]' ;;
  esac
}

safe_id() {
  local id=$1
  case "$id" in
    ""|*/*|*..*|*[!A-Za-z0-9._-]*)
      printf 'Invalid temp command id: %s\n' "$id" >&2
      printf 'Use letters, digits, dot, underscore, or dash.\n' >&2
      exit 2
      ;;
  esac
}

command_path() {
  local id=$1
  safe_id "$id"
  printf '%s/%s.json\n' "$STORE_DIR" "$id"
}

require_command() {
  local id=$1 path
  path=$(command_path "$id")
  [[ -f "$path" ]] || {
    printf 'Unknown temp command: %s\n' "$id" >&2
    printf 'Run: cento temp list\n' >&2
    exit 1
  }
  printf '%s\n' "$path"
}

default_command_id() {
  mkdir -p "$STORE_DIR"
  if [[ -f "$(command_path "$DEFAULT_COMMAND_ID")" ]]; then
    printf '%s\n' "$DEFAULT_COMMAND_ID"
    return 0
  fi
  python3 - "$STORE_DIR" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
paths = sorted(root.glob("*.json"))
if len(paths) == 1:
    try:
        data = json.loads(paths[0].read_text(encoding="utf-8"))
        print(data.get("id") or paths[0].stem)
    except Exception:
        print(paths[0].stem)
    raise SystemExit(0)
if not paths:
    print("No temp commands. Add one with: cento temp add ID --title TITLE --node local --command '...'", file=sys.stderr)
else:
    print("Multiple temp commands exist. Specify one:", file=sys.stderr)
    for path in paths:
        print(f"  {path.stem}", file=sys.stderr)
raise SystemExit(2)
PY
}

json_get() {
  local path=$1 key=$2
  python3 - "$path" "$key" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
value = data.get(sys.argv[2], "")
print(value)
PY
}

copy_to_clipboard() {
  local text=$1
  if command -v pbcopy >/dev/null 2>&1; then
    printf '%s' "$text" | pbcopy
    return 0
  fi
  if command -v wl-copy >/dev/null 2>&1; then
    printf '%s' "$text" | wl-copy
    return 0
  fi
  if command -v xclip >/dev/null 2>&1; then
    printf '%s' "$text" | xclip -selection clipboard
    return 0
  fi
  if command -v xsel >/dev/null 2>&1; then
    printf '%s' "$text" | xsel --clipboard --input
    return 0
  fi
  return 1
}

copy_file_to_clipboard() {
  local path=$1
  if command -v pbcopy >/dev/null 2>&1; then
    pbcopy < "$path"
    return 0
  fi
  if command -v wl-copy >/dev/null 2>&1; then
    wl-copy < "$path"
    return 0
  fi
  if command -v xclip >/dev/null 2>&1; then
    xclip -selection clipboard < "$path" >/dev/null 2>&1 &
    return 0
  fi
  if command -v xsel >/dev/null 2>&1; then
    xsel --clipboard --input < "$path" >/dev/null 2>&1 &
    return 0
  fi
  return 1
}

resolve_repo_path() {
  local path=$1
  case "$path" in
    /*) printf '%s\n' "$path" ;;
    *) printf '%s/%s\n' "$ROOT_DIR" "$path" ;;
  esac
}

clipboard_value_for_log() {
  local log_path=$1
  local diagnostics_path
  diagnostics_path=$(sed -n 's/^Diagnostics written to: //p' "$log_path" | tail -1)
  if [[ -n "$diagnostics_path" ]]; then
    printf '%s\n' "$diagnostics_path"
    return
  fi
  printf '%s\n' "$log_path"
}

add_command() {
  local id=${1:-}
  [[ -n "$id" ]] || { usage >&2; exit 2; }
  safe_id "$id"
  shift

  local title="" node="local" command="" command_file="" copy_file="" description="" force=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --title)
        title=${2:?--title requires a value}
        shift 2
        ;;
      --node)
        node=${2:?--node requires a value}
        shift 2
        ;;
      --command)
        command=${2:?--command requires a value}
        shift 2
        ;;
      --command-file)
        command_file=${2:?--command-file requires a value}
        shift 2
        ;;
      --copy-file)
        copy_file=${2:?--copy-file requires a value}
        shift 2
        ;;
      --description)
        description=${2:?--description requires a value}
        shift 2
        ;;
      --force)
        force=1
        shift
        ;;
      *)
        printf 'Unknown add option: %s\n' "$1" >&2
        usage >&2
        exit 2
        ;;
    esac
  done

  case "$node" in
    local|macos|linux) ;;
    *) printf 'Invalid --node: %s\n' "$node" >&2; exit 2 ;;
  esac
  [[ -n "$title" ]] || title="$id"
  if [[ -n "$command_file" ]]; then
    [[ -f "$command_file" ]] || { printf 'Command file not found: %s\n' "$command_file" >&2; exit 1; }
    command=$(cat "$command_file")
  fi
  if [[ -n "$copy_file" ]]; then
    [[ -z "$command" ]] || { printf 'Use either --copy-file or --command, not both.\n' >&2; exit 2; }
    [[ -f "$(resolve_repo_path "$copy_file")" ]] || { printf 'Copy file not found: %s\n' "$copy_file" >&2; exit 1; }
  else
    [[ -n "$command" ]] || { printf 'Provide --command, --command-file, or --copy-file.\n' >&2; exit 2; }
  fi

  mkdir -p "$STORE_DIR"
  local path
  path=$(command_path "$id")
  if [[ -f "$path" && "$force" -ne 1 ]]; then
    printf 'Temp command already exists: %s\n' "$id" >&2
    printf 'Use --force to replace it.\n' >&2
    exit 1
  fi

  python3 - "$path" "$id" "$title" "$node" "$description" "$command" "$copy_file" <<'PY'
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

path = Path(sys.argv[1])
data = {
    "id": sys.argv[2],
    "title": sys.argv[3],
    "node": sys.argv[4],
    "description": sys.argv[5],
    "command": sys.argv[6],
    "created_at": datetime.now(timezone.utc).isoformat(),
    "created_by": os.environ.get("USER") or os.environ.get("LOGNAME") or "unknown",
}
if sys.argv[7]:
    data["copy_file"] = sys.argv[7]
path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
  printf 'Temp command saved: %s\n' "$id"
  if [[ "$id" == "$DEFAULT_COMMAND_ID" ]]; then
    printf 'Run it with: cento temp run\n'
  else
    printf 'Run it with: cento temp run %s\n' "$id"
  fi
}

list_commands() {
  mkdir -p "$STORE_DIR"
  python3 - "$STORE_DIR" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
rows = []
for path in sorted(root.glob("*.json")):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        rows.append((path.stem, "invalid", "", str(exc)))
        continue
    rows.append((data.get("id", path.stem), data.get("node", ""), data.get("title", ""), data.get("description", "")))

if not rows:
    print("No temp commands. Add one with: cento temp add ID --title TITLE --node local --command '...'")
    raise SystemExit(0)

for ident, node, title, description in rows:
    tail = f" - {description}" if description else ""
    print(f"{ident:<24} {node:<7} {title}{tail}")
PY
}

show_command() {
  local id=${1:-} path
  [[ -n "$id" ]] || id=$(default_command_id)
  path=$(require_command "$id")
  python3 - "$path" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
for key in ("id", "title", "node", "description", "created_at", "created_by"):
    value = data.get(key)
    if value:
        print(f"{key}: {value}")
if data.get("copy_file"):
    print(f"copy_file: {data.get('copy_file')}")
print("command:")
print(data.get("command", ""))
PY
}

run_command() {
  local id=${1:-} dry_run=0 copy_result=1
  if [[ "$id" == "--dry-run" ]]; then
    id=""
  else
    shift || true
  fi
  [[ -n "$id" ]] || id=$(default_command_id)
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --dry-run)
        dry_run=1
        shift
        ;;
      --no-copy)
        copy_result=0
        shift
        ;;
      *)
        printf 'Unknown run option: %s\n' "$1" >&2
        usage >&2
        exit 2
        ;;
    esac
  done

  local path node command copy_file current run_dir log_path status copy_value
  path=$(require_command "$id")
  node=$(json_get "$path" node)
  command=$(json_get "$path" command)
  copy_file=$(json_get "$path" copy_file)
  current=$(platform)

  if [[ -n "$copy_file" ]]; then
    if [[ "$dry_run" -eq 1 ]]; then
      printf 'Would copy file to clipboard: %s\n' "$(resolve_repo_path "$copy_file")"
      return 0
    fi
    if [[ "$node" != "local" && "$node" != "$current" ]]; then
      printf 'copy-file temp commands only run on the local/current node.\n' >&2
      return 1
    fi
    copy_file=$(resolve_repo_path "$copy_file")
    [[ -f "$copy_file" ]] || { printf 'Copy file not found: %s\n' "$copy_file" >&2; return 1; }
    copy_file_to_clipboard "$copy_file" || {
      printf 'Clipboard unavailable. Open prompt manually: %s\n' "$copy_file" >&2
      return 1
    }
    printf 'Copied to clipboard: %s\n' "$copy_file"
    return 0
  fi

  printf 'Temp command: %s\n' "$id"
  printf 'Target node: %s\n' "$node"
  printf 'Command:\n%s\n' "$command"
  if [[ "$dry_run" -eq 1 ]]; then
    return 0
  fi
  printf '\nRunning...\n'

  run_dir="$ROOT_DIR/workspace/runs/temp/history/$(date +%Y%m%d-%H%M%S)-$id"
  mkdir -p "$run_dir"
  log_path="$run_dir/output.log"

  status=0
  if [[ "$node" == "local" || "$node" == "$current" ]]; then
    bash -lc "$command" 2>&1 | tee "$log_path" || status=${PIPESTATUS[0]}
  else
    "$ROOT_DIR/scripts/cento.sh" cluster exec "$node" -- bash -lc "$command" 2>&1 | tee "$log_path" || status=${PIPESTATUS[0]}
  fi

  printf '\nTemp run log: %s\n' "$log_path"
  if [[ "$copy_result" -eq 1 ]]; then
    copy_value=$(clipboard_value_for_log "$log_path")
    if copy_to_clipboard "$copy_value"; then
      printf 'Copied to clipboard: %s\n' "$copy_value"
    else
      printf 'Clipboard unavailable. Copy manually: %s\n' "$copy_value"
    fi
  fi
  return "$status"
}

remove_command() {
  local id=$1 path
  path=$(require_command "$id")
  rm -f "$path"
  printf 'Removed temp command: %s\n' "$id"
}

main() {
  local action=${1:-list}
  shift || true
  case "$action" in
    list|ls)
      list_commands
      ;;
    add|create)
      add_command "$@"
      ;;
    show|cat)
      [[ $# -le 1 ]] || { usage >&2; exit 2; }
      show_command "${1:-}"
      ;;
    run|exec)
      run_command "$@"
      ;;
    remove|rm|delete)
      [[ $# -eq 1 ]] || { usage >&2; exit 2; }
      remove_command "$1"
      ;;
    path)
      mkdir -p "$STORE_DIR"
      printf '%s\n' "$STORE_DIR"
      ;;
    help|-h|--help)
      usage
      ;;
    *)
      printf 'Unknown temp action: %s\n' "$action" >&2
      usage >&2
      exit 2
      ;;
  esac
}

main "$@"
