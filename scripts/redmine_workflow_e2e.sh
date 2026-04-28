#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$SCRIPT_DIR/lib/common.sh"

ROOT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
CRM="$ROOT_DIR/scripts/crm_module.py"
PERSON="E2E Redmine Candidate $(date +%Y%m%d%H%M%S)"
PERSON_SLUG=""
PORT="${PORT:-47931}"
SERVER_PID=""
RUN_LIVE=0

usage() {
    cat <<'USAGE'
Usage: redmine_workflow_e2e.sh [options]

Runs an end-to-end Redmine workflow test through the career-intake system.
By default, it verifies local dry-run behavior and the CRM HTTP endpoint without
requiring a live Redmine instance.

Options:
  --person NAME        Override the generated test person name
  --port PORT          Port for the temporary CRM server
  --live-redmine       Also call the live Redmine API; requires REDMINE_API_KEY
  -h, --help           Show this help
USAGE
}

cleanup() {
    if [[ -n "$SERVER_PID" ]] && kill -0 "$SERVER_PID" >/dev/null 2>&1; then
        kill "$SERVER_PID" >/dev/null 2>&1 || true
        wait "$SERVER_PID" >/dev/null 2>&1 || true
    fi
}

trap cleanup EXIT

log_step() {
    printf '[e2e] %s\n' "$*"
}

assert_file() {
    local path=$1
    [[ -f "$path" ]] || cento_die "Expected file missing: $path"
}

wait_for_server() {
    local url=$1
    local attempt
    for attempt in {1..40}; do
        if curl -fsS "$url/api/state" >/dev/null 2>&1; then
            return 0
        fi
        sleep 0.25
    done
    cento_die "CRM server did not become ready at $url"
}

json_assert() {
    local file=$1
    local expr=$2
    python3 - "$file" "$expr" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text())
expr = sys.argv[2]
if not eval(expr, {"payload": payload}):
    raise SystemExit(f"assertion failed: {expr}")
PY
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --person)
            [[ $# -ge 2 ]] || cento_die "--person requires a name"
            PERSON=$2
            shift 2
            ;;
        --port)
            [[ $# -ge 2 ]] || cento_die "--port requires a port"
            PORT=$2
            shift 2
            ;;
        --live-redmine)
            RUN_LIVE=1
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

cento_require_cmd python3
cento_require_cmd curl

cd "$ROOT_DIR"

log_step "creating intake dossier for: $PERSON"
python3 "$CRM" intake init \
    --person "$PERSON" \
    --target-role "Product Manager" \
    --target-companies "Stripe,Notion,OpenAI,Linear,Figma" \
    --notes "E2E Redmine workflow test." >/tmp/cento-redmine-e2e-init.txt

PERSON_SLUG=$(python3 - "$PERSON" <<'PY'
import re
import sys
slug = re.sub(r"[^a-z0-9]+", "-", sys.argv[1].strip().lower()).strip("-")
print(slug or "career-consulting")
PY
)

DOSSIER="$ROOT_DIR/workspace/runs/career-intake/$PERSON_SLUG"

log_step "adding intake sources"
python3 "$CRM" intake add --person "$PERSON" --kind telegram --title "Telegram conversation" --text "Candidate wants product roles, needs positioning clarity, and has strong operations/customer systems experience." >/tmp/cento-redmine-e2e-add-telegram.txt
python3 "$CRM" intake add --person "$PERSON" --kind resume --title "Resume text" --text "E2E Candidate\nOperations Lead\nImproved onboarding process and reduced manual work." >/tmp/cento-redmine-e2e-add-resume.txt
python3 "$CRM" intake add --person "$PERSON" --kind linkedin --title "LinkedIn text" --text "Operations leader moving toward product management in B2B SaaS and AI tooling." >/tmp/cento-redmine-e2e-add-linkedin.txt

log_step "generating artifact plan"
python3 "$CRM" intake plan --person "$PERSON" --force >/tmp/cento-redmine-e2e-plan.txt

assert_file "$DOSSIER/manifest.json"
assert_file "$DOSSIER/artifact-plan.md"
assert_file "$DOSSIER/prompts/top-5-cover-letter-pack.md"
assert_file "$DOSSIER/artifacts/top-5-cover-letter-pack.md"

log_step "validating CLI Redmine dry-run"
CLI_JSON=/tmp/cento-redmine-e2e-cli.json
python3 "$CRM" integration --provider redmine --person "$PERSON" --start-workflow --dry-run > "$CLI_JSON"
json_assert "$CLI_JSON" "payload['ok'] is True"
json_assert "$CLI_JSON" "payload['dry_run'] is True"
json_assert "$CLI_JSON" "len(payload['issues']) == 7"
json_assert "$CLI_JSON" "payload['project_identifier'].startswith('career-')"

log_step "starting temporary CRM server on port $PORT"
python3 "$CRM" serve --host 127.0.0.1 --port "$PORT" >/tmp/cento-redmine-e2e-server.log 2>&1 &
SERVER_PID=$!
wait_for_server "http://127.0.0.1:$PORT"

log_step "validating HTTP Redmine endpoint dry-run"
HTTP_JSON=/tmp/cento-redmine-e2e-http.json
curl -fsS "http://127.0.0.1:$PORT/api/integrations/redmine/start-workflow" \
    -H 'Content-Type: application/json' \
    -d "{\"person\":\"$PERSON\",\"dry_run\":true}" > "$HTTP_JSON"
json_assert "$HTTP_JSON" "payload['ok'] is True"
json_assert "$HTTP_JSON" "payload['dry_run'] is True"
json_assert "$HTTP_JSON" "len(payload['issues']) == 7"

if [[ "$RUN_LIVE" -eq 1 ]]; then
    [[ -n "${REDMINE_API_KEY:-}" ]] || cento_die "--live-redmine requires REDMINE_API_KEY"
    log_step "running live Redmine workflow"
    LIVE_JSON=/tmp/cento-redmine-e2e-live.json
    python3 "$CRM" integration --provider redmine --person "$PERSON" --start-workflow > "$LIVE_JSON"
    json_assert "$LIVE_JSON" "payload['ok'] is True"
    json_assert "$LIVE_JSON" "payload['dry_run'] is False"
fi

log_step "passed"
printf 'person=%s\n' "$PERSON"
printf 'dossier=%s\n' "$DOSSIER"
printf 'cli_result=%s\n' "$CLI_JSON"
printf 'http_result=%s\n' "$HTTP_JSON"
