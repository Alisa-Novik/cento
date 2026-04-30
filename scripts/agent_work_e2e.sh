#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
CENTO="$ROOT_DIR/scripts/cento.sh"

export CENTO_BIN="$CENTO"

title="Cento Agent Work E2E $(date +%Y%m%d-%H%M%S)"

"$CENTO" agent-work bootstrap >/dev/null

created_json=$(
  "$CENTO" agent-work create \
    --title "$title" \
    --description "E2E probe for the Cento agent work tracker." \
    --node linux \
    --agent e2e \
    --package e2e \
    --json
)

issue_id=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"$created_json")
[[ "$issue_id" =~ ^[0-9]+$ ]]

"$CENTO" agent-work claim "$issue_id" --node linux --agent e2e --note "E2E claimed." >/dev/null
"$CENTO" agent-work update "$issue_id" --status review --note "E2E moved to review." >/dev/null
"$CENTO" agent-work dispatch "$issue_id" --node linux --agent e2e --dry-run | grep -F "issue-$issue_id-" >/dev/null

done_json=$("$CENTO" agent-work update "$issue_id" --status done --note "E2E complete." --json)
status=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])' <<<"$done_json")
[[ "$status" == "Done" ]]

list_json=$("$CENTO" agent-work list --all --json)
python3 -c 'import json,sys
issue_id = int(sys.argv[1])
title = sys.argv[2]
payload = json.load(sys.stdin)
for issue in payload["issues"]:
    if issue["id"] == issue_id and issue["subject"] == title and issue["status"] == "Done":
        raise SystemExit(0)
raise SystemExit(f"missing closed E2E issue #{issue_id}: {title}")' "$issue_id" "$title" <<<"$list_json"

printf 'agent-work e2e ok: #%s %s\n' "$issue_id" "$title"
