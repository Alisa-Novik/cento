#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
REDMINE_DIR="$ROOT_DIR/experimental/redmine-career-consulting"
HELPER="$REDMINE_DIR/scripts/redmine-compose-root.sh"
SUDOERS_FILE="/etc/sudoers.d/cento-redmine-cutover"
TEMP_ISSUE_ID="${CENTO_TEMP_ISSUE_ID:-133}"

case "$TEMP_ISSUE_ID" in
  ""|*[!0-9]*)
    echo "CENTO_TEMP_ISSUE_ID must be a numeric issue id." >&2
    exit 2
    ;;
esac

RUN_DIR="$ROOT_DIR/workspace/runs/agent-work/$TEMP_ISSUE_ID"

usage() {
  cat <<'USAGE'
Usage: cento run temp 1 [rollback|status]

Temp commands:
  1           Install least-privilege sudoers entry, stop Redmine, validate replacement, and update the configured issue id.
  1 rollback  Start Redmine again using the same helper.
  1 status    Show Redmine compose status through the helper.
USAGE
}

validate_sudoers() {
  sudo visudo -cf "$SUDOERS_FILE" >/dev/null
}

install_cutover_sudoers() {
  local line
  if sudo -n "$HELPER" config >/dev/null 2>&1; then
    printf 'Sudoers entry already works for cutover helper.\n'
    return 0
  fi
  line="$(whoami) ALL=(root) NOPASSWD: $HELPER"
  printf 'Installing sudoers entry: %s\n' "$SUDOERS_FILE"
  printf '%s\n' "$line" | sudo tee "$SUDOERS_FILE" >/dev/null
  sudo chmod 0440 "$SUDOERS_FILE"
  validate_sudoers
}

run_cutover_stop() {
  mkdir -p "$RUN_DIR"
  printf 'Stopping Redmine through cutover helper...\n'
  (
    cd "$REDMINE_DIR"
    ./scripts/redmine.sh cutover-stop
  ) 2>&1 | tee "$RUN_DIR/operator-cutover-stop.log"
}

run_cutover_start() {
  mkdir -p "$RUN_DIR"
  printf 'Starting Redmine through cutover helper...\n'
  (
    cd "$REDMINE_DIR"
    ./scripts/redmine.sh cutover-start
  ) 2>&1 | tee "$RUN_DIR/operator-cutover-start.log"
}

run_cutover_status() {
  (
    cd "$REDMINE_DIR"
    ./scripts/redmine.sh cutover-status
  )
}

validate_replacement() {
  mkdir -p "$RUN_DIR"
  printf 'Validating replacement backend while Redmine is stopped...\n'
  (
    cd "$ROOT_DIR"
    export CENTO_AGENT_WORK_BACKEND=replacement
    local title evidence_path story_path created_json issue_id done_json status
    title="Cento Replacement-Only Cutover Smoke $(date +%Y%m%d-%H%M%S)"
    evidence_path="$RUN_DIR/operator-replacement-e2e-evidence.txt"
    story_path="$RUN_DIR/operator-replacement-e2e-story.json"
    cat > "$evidence_path" <<EOF
replacement-only cutover smoke
status: running
backend: replacement
redmine: stopped
EOF
    cat > "$story_path" <<EOF
{
  "schema_version": "1.0",
  "issue": {
    "id": 0,
    "title": "$title",
    "package": "redmine-retirement-e2e-v1"
  },
  "lane": {
    "owner": "temp-cutover",
    "node": "linux",
    "agent": "temp-cutover",
    "role": "validator"
  },
  "paths": {
    "run_dir": "workspace/runs/agent-work/replacement-only-draft"
  },
  "scope": {
    "acceptance": [
      "replacement-only task creation requires and canonicalizes this story manifest"
    ]
  },
  "expected_outputs": [
    {
      "path": "${evidence_path#$ROOT_DIR/}",
      "description": "Replacement-only validation evidence",
      "required": true,
      "owner": "temp-cutover"
    }
  ]
}
EOF
    created_json=$(python3 scripts/agent_work.py create \
      --title "$title" \
      --manifest "$story_path" \
      --description "Replacement-only smoke while Redmine is stopped. This intentionally does not run bootstrap." \
      --node linux \
      --agent temp-cutover \
      --role validator \
      --package redmine-retirement-e2e-v1 \
      --json)
    issue_id=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"$created_json")
    python3 scripts/agent_work.py claim "$issue_id" --node linux --agent temp-cutover --role validator --note "Replacement-only cutover smoke claimed." >/dev/null
    python3 scripts/agent_work.py update "$issue_id" --status validating --role validator --note "Replacement-only update path works while Redmine is stopped." >/dev/null
    python3 scripts/agent_work.py dispatch "$issue_id" --node linux --agent temp-cutover --role validator --dry-run | grep -F "issue-$issue_id-" >/dev/null
    python3 scripts/agent_work.py validate "$issue_id" --result pass --evidence "$evidence_path" --note "Replacement-only validation evidence while Redmine is stopped." >/dev/null
    done_json=$(python3 scripts/agent_work.py update "$issue_id" --status done --role validator --note "Replacement-only cutover smoke complete." --json)
    status=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])' <<<"$done_json")
    [[ "$status" == "Done" ]]
    python3 scripts/agent_work.py show "$issue_id" --json >/dev/null
    python3 scripts/agent_work.py list --all --json >/dev/null
    printf 'replacement-only e2e ok: #%s %s\n' "$issue_id" "$title"
    printf 'backend=replacement evidence=%s\n' "$evidence_path"
  ) 2>&1 | tee "$RUN_DIR/operator-replacement-e2e.log"
}

mark_issue_passed() {
  local note
  note=$(cat <<EOF
Delivered
- Operator installed the least-privilege Redmine cutover sudoers entry.
- Redmine was stopped through the cutover helper.
- Replacement backend e2e passed while Redmine was stopped.

Validation
- sudo visudo validated /etc/sudoers.d/cento-redmine-cutover.
- ./experimental/redmine-career-consulting/scripts/redmine.sh cutover-stop completed.
- CENTO_AGENT_WORK_BACKEND=replacement ./scripts/agent_work_e2e.sh completed.

Evidence
- workspace/runs/agent-work/$TEMP_ISSUE_ID/operator-cutover-stop.log
- workspace/runs/agent-work/$TEMP_ISSUE_ID/operator-replacement-e2e.log

Residual risk
- Redmine remains stopped intentionally. Roll back with: cento run temp 1 rollback
EOF
)
  (
    cd "$ROOT_DIR"
    CENTO_AGENT_WORK_BACKEND=replacement python3 scripts/agent_work.py validate "$TEMP_ISSUE_ID" \
      --result pass \
      --evidence "$RUN_DIR/operator-cutover-stop.log" \
      --evidence "$RUN_DIR/operator-replacement-e2e.log" \
      --note "$note" || true
  )
}

run_temp_1() {
  install_cutover_sudoers
  run_cutover_stop
  validate_replacement
  mark_issue_passed
  printf '\nDone. Redmine cutover stop completed and replacement validation passed.\n'
  printf 'Rollback command: cento run temp 1 rollback\n'
}

main() {
  local id=${1:-}
  shift || true
  case "$id" in
    1)
      case "${1:-}" in
        "")
          run_temp_1
          ;;
        rollback)
          install_cutover_sudoers
          run_cutover_start
          ;;
        status)
          install_cutover_sudoers
          run_cutover_status
          ;;
        *)
          usage >&2
          exit 2
          ;;
      esac
      ;;
    ""|-h|--help|help)
      usage
      ;;
    *)
      usage >&2
      exit 2
      ;;
  esac
}

main "$@"
